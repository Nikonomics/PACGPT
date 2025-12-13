"""
RAG Engine for Idaho ALF RegNavigator
Combines vector search and Claude API for question answering.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from embeddings import ChunkEmbeddingManager, create_embedding_generator
from ai_service import ai_service


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
        similarity_threshold: float = 0.0
    ) -> List[Dict]:
        """
        Retrieve most relevant chunks for a query.

        Args:
            query: User question
            top_k: Number of chunks to retrieve
            similarity_threshold: Minimum similarity score (0.0-1.0)

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
        verbose: bool = False
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

        Returns:
            Dict with answer, citations, and metadata
        """
        if verbose:
            print(f"\n{'='*80}")
            print(f"QUESTION: {question}")
            print(f"{'='*80}\n")

        # Step 1: Retrieve relevant chunks
        if verbose:
            print("Retrieving relevant regulations...")

        results = self.retrieve_relevant_chunks(
            question,
            top_k=top_k,
            similarity_threshold=similarity_threshold
        )

        retrieved_chunks = [r["chunk"] for r in results]

        if verbose:
            print(f"✓ Retrieved {len(retrieved_chunks)} relevant chunks:\n")
            for i, result in enumerate(results, 1):
                chunk = result["chunk"]
                similarity = result["similarity"]
                print(f"  {i}. {chunk['citation']} - {chunk['section_title']}")
                print(f"     Similarity: {similarity:.4f}\n")

        # Step 2: Generate answer with Claude
        if verbose:
            print("Generating answer with Claude...\n")

        # Build prompt for AI service
        prompt = self._build_prompt(question, retrieved_chunks, conversation_history)
        
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
                    'citation': chunk['citation'],
                    'section_title': chunk['section_title'],
                    'chunk_id': chunk['chunk_id']
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

    def _build_prompt(self, question: str, retrieved_chunks: List[Dict], conversation_history: Optional[List[Dict]] = None) -> str:
        """Build prompt for AI service."""
        # System prompt
        system_prompt = """You are a helpful regulatory compliance expert for Idaho assisted living facilities. Your job is to give PRACTICAL, CONCRETE answers that administrators and operators can actually use.

PRIORITY: Answer the question directly with specific numbers, requirements, and actionable information.

HOW TO RESPOND:
1. **Lead with the concrete answer** - If someone asks about staffing, give them numbers. If they ask about square footage, give them the measurements. Don't bury the answer in legal language.

2. **Extract specific requirements** from the regulations:
   - Exact numbers (ratios, square feet, temperatures, hours)
   - Specific qualifications or certifications required
   - Clear yes/no when applicable
   - Deadlines or timeframes

3. **Use plain language** - Translate regulatory jargon into practical terms an operator can understand and act on.

4. **Cite your sources** - Use inline citations [1], [2], etc. but ONLY cite regulations that are actually relevant to the answer. Don't pad with tangential citations.

5. **Acknowledge gaps** - If the regulations don't specify an exact number or requirement, say so clearly. Don't hedge with vague language.

EXAMPLE OF A GOOD ANSWER:
Question: "What are the staffing requirements for a 20-bed facility?"
Good: "For a 20-bed facility, you need:
- At least 1 staff member present in each building/unit at all times when residents are present [1]
- At least 1 direct care staff with current First Aid and CPR certification on duty at all times [2]
- Staff must be awake during residents' sleeping hours [1]

Note: Idaho regulations don't specify exact staff-to-resident ratios - staffing must be 'sufficient' based on resident needs per your negotiated service agreements [2]."

BAD: "According to the regulations, staffing policies must be developed and implemented based on various factors including the number of residents..."

Context from regulations (numbered [1], [2], [3], etc.):"""

        # Add retrieved chunks with numbered citations (increased from 1000 to 2000 chars per chunk)
        context = "\n\n".join([
            f"[{i+1}] **{chunk['citation']} - {chunk['section_title']}**\n{chunk['content'][:2000]}..."
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
