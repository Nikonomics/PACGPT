"""
RAG Engine for Idaho ALF RegNavigator
Combines vector search and Claude API for question answering.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from embeddings import ChunkEmbeddingManager, create_embedding_generator
from ai_service import ai_service


def get_citation(chunk: dict) -> str:
    """Get citation from chunk, handling array and singular field formats."""
    # First check for "citations" array (used by Arizona chunks)
    citations_list = chunk.get('citations', [])
    if citations_list:
        return citations_list[0]
    # Fall back to singular "citation" field
    if chunk.get('citation'):
        return chunk.get('citation')
    # Fall back to section_number
    return chunk.get('section_number', 'N/A')


class RAGEngine:
    """Retrieval-Augmented Generation engine for regulatory Q&A."""

    def __init__(
        self,
        chunks_with_embeddings_path: str,
        embedding_provider: str = "openai",
        claude_model: str = "claude-sonnet-4-20250514",
        embedding_api_key: Optional[str] = None,
        claude_api_key: Optional[str] = None
    ):
        """
        Initialize RAG engine.

        Args:
            chunks_with_embeddings_path: Path to JSON file with chunks and embeddings
            embedding_provider: "voyage" or "openai"
            claude_model: Claude model to use
            embedding_api_key: API key for embedding provider
            claude_api_key: Anthropic API key
        """
        self.chunks_with_embeddings_path = Path(chunks_with_embeddings_path)

        # Load chunks with embeddings
        print(f"Loading chunks from {self.chunks_with_embeddings_path}...")
        with open(self.chunks_with_embeddings_path, 'r', encoding='utf-8') as f:
            self.chunks = json.load(f)
        print(f"✓ Loaded {len(self.chunks)} chunks")

        # Initialize embedding generator
        self.embedding_generator = create_embedding_generator(
            provider=embedding_provider,
            api_key=embedding_api_key
        )
        print(f"✓ Embedding generator initialized ({embedding_provider})")

        # Initialize embedding manager
        self.embedding_manager = ChunkEmbeddingManager(
            self.embedding_generator,
            str(self.chunks_with_embeddings_path.parent)
        )

        # Use unified AI service instead of direct Claude client
        self.ai_service = ai_service
        print(f"✓ AI service initialized (unified with fallback)")

    def retrieve_relevant_chunks(
        self,
        query: str,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        state: Optional[str] = None,
        topic_tags: Optional[List[str]] = None,
        facility_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Retrieve most relevant chunks for a query.

        Args:
            query: User question
            top_k: Number of chunks to retrieve
            similarity_threshold: Minimum similarity score (0.0-1.0)
            state: State to filter by (e.g., "Idaho", "Washington", "Oregon")
                   If provided, returns state-specific + federal (jurisdiction="All") chunks
            topic_tags: List of topic tags to filter by (e.g., ["staffing", "licensing"])
                        Chunk must have at least one matching tag
            facility_type: Facility type to filter by (e.g., "ALF", "SNF", "Both", "General")
                          Matches chunk's facility_types if it equals the type, "General", or "Both"

        Returns:
            List of relevant chunks with similarity scores
        """
        # Generate query embedding
        query_embedding = self.embedding_generator.generate_embedding(query)

        # Compute similarities
        similarities = []
        for chunk in self.chunks:
            if "embedding" not in chunk:
                continue

            # Apply jurisdiction filter if state is specified
            if state:
                jurisdiction = chunk.get("jurisdiction", "")
                # Include chunks from the specified state OR federal chunks (jurisdiction="All")
                if jurisdiction != state and jurisdiction != "All":
                    continue

            # Apply topic_tags filter if specified
            if topic_tags:
                chunk_tags = chunk.get("topic_tags", [])
                # Check if chunk has at least one matching tag
                if not any(tag in chunk_tags for tag in topic_tags):
                    continue

            # Apply facility_type filter if specified
            if facility_type:
                # Check both "facility_types" and "facility_type" for compatibility
                chunk_facility = chunk.get("facility_types") or chunk.get("facility_type", "")

                # Handle facility_types as list (e.g., ['ALF']) or string
                if isinstance(chunk_facility, list):
                    # Include if list contains requested type, "General", "Both", or "All"
                    if not any(f in [facility_type, "General", "Both", "All"] for f in chunk_facility):
                        continue
                else:
                    # String comparison - include if matches requested type, or is "General", "Both", or "All"
                    if chunk_facility not in [facility_type, "General", "Both", "All"]:
                        continue

            similarity = self.embedding_manager.compute_similarity(
                query_embedding,
                chunk["embedding"]
            )

            if similarity >= similarity_threshold:
                similarities.append({
                    "chunk": chunk,
                    "similarity": similarity
                })

        # Sort by similarity
        similarities.sort(key=lambda x: x["similarity"], reverse=True)

        # Return top k
        return similarities[:top_k]

    def answer_question(
        self,
        question: str,
        conversation_history: Optional[List[Dict]] = None,
        top_k: int = 12,  # Increased from 5 for better context
        similarity_threshold: float = 0.0,  # Lowered from 0.3 to get more chunks
        temperature: float = 0.5,  # Increased from 0.3 for more natural responses
        verbose: bool = False,
        state: Optional[str] = None,  # State filter for jurisdiction-specific queries
        topic_tags: Optional[List[str]] = None,  # Topic tags filter
        facility_type: Optional[str] = None  # Facility type filter
    ) -> Dict:
        """
        Answer a question using RAG.

        Args:
            question: User question
            conversation_history: Previous conversation messages
            top_k: Number of chunks to retrieve
            similarity_threshold: Minimum similarity for retrieval
            temperature: Temperature for Claude response
            verbose: Print debug information
            state: State to filter by (e.g., "Idaho", "Washington", "Oregon")
            topic_tags: List of topic tags to filter by (e.g., ["staffing", "licensing"])
            facility_type: Facility type to filter by (e.g., "ALF", "SNF", "Both", "General")

        Returns:
            Dict with answer, citations, and metadata
        """
        if verbose:
            print(f"\n{'='*80}")
            print(f"QUESTION: {question}")
            if state:
                print(f"STATE CONTEXT: {state}")
            print(f"{'='*80}\n")

        # Step 1: Retrieve relevant chunks (filtered by state if provided)
        if verbose:
            print(f"Retrieving relevant regulations{f' for {state}' if state else ''}...")

        results = self.retrieve_relevant_chunks(
            question,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            state=state,
            topic_tags=topic_tags,
            facility_type=facility_type
        )

        retrieved_chunks = [r["chunk"] for r in results]

        if verbose:
            print(f"✓ Retrieved {len(retrieved_chunks)} relevant chunks:\n")
            for i, result in enumerate(results, 1):
                chunk = result["chunk"]
                similarity = result["similarity"]
                # Handle array and singular citation formats
                citation = get_citation(chunk)
                title = chunk.get('section_title', 'N/A')
                print(f"  {i}. {citation} - {title}")
                print(f"     Similarity: {similarity:.4f}\n")

        # Step 2: Generate answer with Claude
        if verbose:
            print("Generating answer with Claude...\n")

        # Build prompt for AI service
        prompt = self._build_prompt(question, retrieved_chunks, conversation_history, state)
        
        # Use unified AI service with fallback
        ai_response = self.ai_service.analyze_content(prompt, {
            'maxTokens': 3000,  # Increased from 2048 for more detailed answers
            'temperature': temperature
        })
        
        # Parse response
        response_text = ai_response['content']
        
        # Validate that all citations are used in the response
        import re
        used_citations = set(re.findall(r'\[(\d+)\]', response_text))
        expected_citations = set(str(i+1) for i in range(len(retrieved_chunks)))
        missing_citations = expected_citations - used_citations
        
        if missing_citations and verbose:
            print(f"⚠️  WARNING: Citations not used in response: {sorted(missing_citations, key=int)}")
            print(f"   Used citations: {sorted(used_citations, key=int)}")
            print(f"   Expected citations: {sorted(expected_citations, key=int)}")
        
        response = {
            'response': response_text,
            'citations': [
                {
                    'citation': get_citation(chunk),
                    'section_title': chunk.get('section_title', 'N/A'),
                    'chunk_id': chunk.get('chunk_id', 'N/A'),
                    'content': chunk.get('content', ''),
                    'source_document': chunk.get('source_file') or chunk.get('source_document', 'N/A')
                }
                for chunk in retrieved_chunks
            ],
            'usage': {
                'provider': ai_response['provider'],
                'chunks_retrieved': len(retrieved_chunks),
                'citations_used': len(used_citations),
                'citations_expected': len(expected_citations),
                'missing_citations': sorted(missing_citations, key=int) if missing_citations else []
            }
        }

        if verbose:
            print("✓ Answer generated\n")

        # Add similarity scores to response
        response["retrieved_chunks"] = [
            {
                **chunk,
                "similarity": result["similarity"]
            }
            for result, chunk in zip(results, retrieved_chunks)
        ]

        return response

    def _build_prompt(self, question: str, retrieved_chunks: List[Dict], conversation_history: Optional[List[Dict]] = None, state: Optional[str] = None) -> str:
        """Build prompt for AI service."""
        # State-specific context
        state_name = state or "Idaho"

        # System prompt with dynamic state
        system_prompt = f"""You are a helpful regulatory compliance expert for {state_name} assisted living facilities. Your job is to give PRACTICAL, CONCRETE answers that administrators and operators can actually use.

IMPORTANT: You are answering questions specifically for {state_name}. Your response should be based on {state_name} regulations and applicable federal requirements.

PRIORITY: Answer the question directly with specific numbers, requirements, and actionable information.

HOW TO RESPOND:
**CRITICAL: Base your answer ONLY on information from the provided context below. If the context contains relevant information, USE IT to answer the question - don't be overly cautious. Only say "I don't have information about that in the {state_name} regulations I have access to" if the retrieved context truly has nothing relevant to the question. Never use your general training knowledge to answer regulatory questions.**

**CITATION RULE: Only cite OAR, WAC, IDAPA, or other regulatory section numbers that appear VERBATIM in the provided context. If the context does not contain a specific section number, do NOT invent one. Instead say "per Oregon regulations" or "according to the facility requirements" without fabricating a citation number. Never generate a citation like "OAR 411-054-0300" unless that exact string appears in the retrieved text.**

1. **Lead with the concrete answer** - If someone asks about staffing, give them numbers. If they ask about square footage, give them the measurements. Don't bury the answer in legal language.

2. **Extract specific requirements** from the regulations:
   - Exact numbers (ratios, square feet, temperatures, hours)
   - Specific qualifications or certifications required
   - Clear yes/no when applicable
   - Deadlines or timeframes

3. **Use plain language** - Translate regulatory jargon into practical terms an operator can understand and act on.

4. **Cite your sources** - Use inline citations [1], [2], etc. but ONLY cite regulations that are actually relevant to the answer. Don't pad with tangential citations.

5. **Acknowledge gaps** - If the regulations don't specify an exact number or requirement, say so clearly. Don't hedge with vague language.

6. **Note the jurisdiction** - When citing regulations, note whether they are {state_name}-specific state regulations or federal requirements that apply to all states.

EXAMPLE OF A GOOD ANSWER:
Question: "What are the staffing requirements for a 20-bed facility?"
Good: "Based on {state_name} regulations, for a 20-bed facility you need:
- At least 1 staff member present in each building/unit at all times when residents are present [1]
- At least 1 direct care staff with current First Aid and CPR certification on duty at all times [2]
- Staff must be awake during residents' sleeping hours [1]

Note: {state_name} regulations don't specify exact staff-to-resident ratios - staffing must be 'sufficient' based on resident needs per your negotiated service agreements [2]."

BAD: "According to the regulations, staffing policies must be developed and implemented based on various factors including the number of residents..."

Context from {state_name} and federal regulations (numbered [1], [2], [3], etc.):"""

        # Add retrieved chunks with numbered citations (increased from 1000 to 2000 chars per chunk)
        # Handle array and singular citation formats
        context = "\n\n".join([
            f"[{i+1}] **{get_citation(chunk)} - {chunk.get('section_title', 'N/A')}**\n{chunk.get('content', '')[:2000]}..."
            for i, chunk in enumerate(retrieved_chunks)
        ])

        # Add conversation history if provided
        history_text = ""
        if conversation_history:
            history_text = "\n\nPrevious conversation:\n"
            for msg in conversation_history[-3:]:  # Last 3 messages
                history_text += f"{msg['role']}: {msg['content']}\n"

        # Combine everything
        prompt = f"{system_prompt}\n\n{context}\n\n{history_text}\n\nQuestion: {question}\n\nRemember: Give a direct, practical answer with specific numbers and requirements. Use citations [1], [2], etc. for the regulations you reference. If the regulations don't specify something exactly, say so.\n\nAnswer:"
        
        return prompt

    def answer_question_streaming(
        self,
        question: str,
        conversation_history: Optional[List[Dict]] = None,
        top_k: int = 5,
        similarity_threshold: float = 0.3,
        temperature: float = 0.3
    ):
        """
        Answer a question with streaming response.

        Args:
            question: User question
            conversation_history: Previous conversation messages
            top_k: Number of chunks to retrieve
            similarity_threshold: Minimum similarity for retrieval
            temperature: Temperature for Claude response

        Yields:
            Response text chunks
        """
        # Retrieve relevant chunks
        results = self.retrieve_relevant_chunks(
            question,
            top_k=top_k,
            similarity_threshold=similarity_threshold
        )

        retrieved_chunks = [r["chunk"] for r in results]

        # Stream response from Claude
        for text_chunk in self.claude_client.generate_response_streaming(
            query=question,
            retrieved_chunks=retrieved_chunks,
            conversation_history=conversation_history,
            temperature=temperature
        ):
            yield text_chunk


def main():
    """Test RAG engine with sample questions."""
    import os

    # Path to chunks with embeddings
    chunks_path = "/Users/nikolashulewsky/snf-news-aggregator/idaho-alf-chatbot/data/processed/chunks_with_embeddings.json"

    if not Path(chunks_path).exists():
        print(f"ERROR: {chunks_path} not found")
        print("Run embeddings.py first to generate embeddings")
        return

    print("="*80)
    print("IDAHO ALF REGNAVIGATOR - RAG ENGINE TEST")
    print("="*80 + "\n")

    # Initialize RAG engine
    rag = RAGEngine(
        chunks_with_embeddings_path=chunks_path,
        embedding_provider="openai"
    )

    print("\n" + "="*80)
    print("TESTING WITH SAMPLE QUESTIONS")
    print("="*80 + "\n")

    # Test questions
    test_questions = [
        "What are the staffing requirements for a 20-bed facility?",
        "How much square footage is required per resident?",
        "What are the bathroom requirements?",
        "Do I need a sprinkler system?",
        "Can staff assist with insulin?"
    ]

    for i, question in enumerate(test_questions, 1):
        result = rag.answer_question(
            question,
            top_k=3,
            verbose=True
        )

        print("="*80)
        print(f"ANSWER {i}")
        print("="*80)
        print(result["response"])

        print("\n" + "-"*80)
        print("CITATIONS")
        print("-"*80)
        for citation in result["citations"]:
            print(f"• {citation['citation']}: {citation['section_title']}")

        print("\n" + "-"*80)
        print(f"Tokens: {result['usage']['input_tokens']} in, {result['usage']['output_tokens']} out")
        print("-"*80 + "\n")

        if i < len(test_questions):
            input("Press Enter for next question...")


if __name__ == "__main__":
    main()
