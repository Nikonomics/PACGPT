"""
Improved RAG Engine for Idaho ALF RegNavigator
Enhanced with better retrieval, reranking, and prompt optimization.
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from embeddings import ChunkEmbeddingManager, create_embedding_generator
from ai_service import ai_service
import numpy as np


class ImprovedRAGEngine:
    """Enhanced RAG engine with better retrieval and reranking."""

    def __init__(
        self,
        chunks_with_embeddings_path: str,
        embedding_provider: str = "openai",
        claude_model: str = "claude-sonnet-4-20250514",
        embedding_api_key: Optional[str] = None,
        claude_api_key: Optional[str] = None
    ):
        """
        Initialize improved RAG engine.

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

        # Use unified AI service
        self.ai_service = ai_service
        print(f"✓ AI service initialized (unified with fallback)")

    def retrieve_relevant_chunks(
        self,
        query: str,
        top_k: int = 15,  # Increased from 5
        similarity_threshold: float = 0.0,  # Lowered from 0.3
        diversity_threshold: float = 0.05  # NEW: minimum difference between chunks
    ) -> List[Dict]:
        """
        Retrieve most relevant chunks with diversity.

        Args:
            query: User question
            top_k: Number of chunks to retrieve
            similarity_threshold: Minimum similarity score (0.0-1.0)
            diversity_threshold: Minimum difference between chunks to ensure diversity

        Returns:
            List of relevant chunks with similarity scores
        """
        # Generate query embedding
        query_embedding = self.embedding_generator.generate_embedding(query)

        # Compute similarities for ALL chunks
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

        # Apply diversity filtering to avoid duplicate chunks
        diverse_results = []
        for result in similarities:
            if not diverse_results:
                diverse_results.append(result)
            else:
                # Check if this chunk is sufficiently different from already selected chunks
                is_diverse = True
                for selected in diverse_results:
                    # Compute similarity between chunks
                    chunk_sim = self.embedding_manager.compute_similarity(
                        result["chunk"]["embedding"],
                        selected["chunk"]["embedding"]
                    )
                    # If chunks are too similar, skip this one
                    if chunk_sim > (1 - diversity_threshold):
                        is_diverse = False
                        break
                
                if is_diverse:
                    diverse_results.append(result)
            
            # Stop when we have enough diverse chunks
            if len(diverse_results) >= top_k:
                break

        return diverse_results

    def answer_question(
        self,
        question: str,
        conversation_history: Optional[List[Dict]] = None,
        top_k: int = 12,  # Increased from 5
        similarity_threshold: float = 0.0,  # Lowered from 0.3
        temperature: float = 0.5,  # Increased from 0.3
        max_content_length: int = 2000,  # Increased from 1000
        verbose: bool = False
    ) -> Dict:
        """
        Answer a question using improved RAG.

        Args:
            question: User question
            conversation_history: Previous conversation messages
            top_k: Number of chunks to retrieve
            similarity_threshold: Minimum similarity for retrieval
            temperature: Temperature for Claude response
            max_content_length: Maximum characters per chunk in prompt
            verbose: Print debug information

        Returns:
            Dict with answer, citations, and metadata
        """
        if verbose:
            print(f"\n{'='*80}")
            print(f"QUESTION: {question}")
            print(f"{'='*80}\n")

        # Step 1: Retrieve relevant chunks with diversity
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
                
                # Color code similarity
                if similarity >= 0.7:
                    status = "🟢 Excellent"
                elif similarity >= 0.5:
                    status = "🟡 Good"
                elif similarity >= 0.3:
                    status = "🟠 Fair"
                else:
                    status = "🔴 Poor"
                
                print(f"  {i}. {status} (Similarity: {similarity:.4f})")
                print(f"     {chunk['citation']} - {chunk['section_title']}\n")

        # Step 2: Generate answer with Claude
        if verbose:
            print("Generating answer with Claude...\n")

        # Build improved prompt
        prompt = self._build_improved_prompt(
            question, 
            retrieved_chunks, 
            conversation_history,
            max_content_length
        )
        
        # Use unified AI service with fallback
        ai_response = self.ai_service.analyze_content(prompt, {
            'maxTokens': 3000,  # Increased from 2048
            'temperature': temperature
        })
        
        # Parse response
        response = {
            'response': ai_response['content'],
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
                'avg_similarity': np.mean([r["similarity"] for r in results])
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

    def _build_improved_prompt(
        self, 
        question: str, 
        retrieved_chunks: List[Dict], 
        conversation_history: Optional[List[Dict]] = None,
        max_content_length: int = 2000
    ) -> str:
        """Build improved prompt with better context and instructions."""
        
        # Enhanced system prompt
        system_prompt = """You are a regulatory compliance expert for Idaho assisted living facilities. Your role:
- Answer questions about IDAPA regulations accurately and comprehensively
- Provide clear, practical explanations in plain English
- Always cite specific sections (e.g., "According to IDAPA 16.03.22.600...")
- Be thorough - if multiple regulations apply, mention them all
- If information is not in the provided context, say so clearly
- Format your response with clear structure and examples

Response format:
1. **Direct Answer** - Clear, concise answer to the question
2. **Regulatory Requirements** - Specific citations and requirements
3. **Practical Implications** - What this means for facility operations
4. **Related Regulations** - Other relevant sections if applicable

Context from regulations:"""

        # Build context with better formatting and more content
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, 1):
            # Include more content per chunk
            content = chunk['content']
            if len(content) > max_content_length:
                content = content[:max_content_length] + "..."
            
            context_parts.append(
                f"\n[{i}] {chunk['citation']} - {chunk['section_title']}\n"
                f"{content}"
            )
        
        context = "\n".join(context_parts)

        # Add conversation history if provided
        history_text = ""
        if conversation_history:
            history_text = "\n\nPrevious conversation:\n"
            for msg in conversation_history[-5:]:  # Last 5 messages (increased from 3)
                role = "User" if msg['role'] == 'user' else "Assistant"
                history_text += f"{role}: {msg['content']}\n"

        # Combine everything
        prompt = f"{system_prompt}\n{context}\n{history_text}\n\nQuestion: {question}\n\nProvide a comprehensive answer:"
        
        return prompt

    def get_retrieval_stats(self, question: str) -> Dict:
        """Get statistics about retrieval quality for a question."""
        results = self.retrieve_relevant_chunks(question, top_k=15, similarity_threshold=0.0)
        
        if not results:
            return {
                "total_chunks": 0,
                "avg_similarity": 0,
                "max_similarity": 0,
                "min_similarity": 0
            }
        
        similarities = [r["similarity"] for r in results]
        
        return {
            "total_chunks": len(results),
            "avg_similarity": np.mean(similarities),
            "max_similarity": np.max(similarities),
            "min_similarity": np.min(similarities),
            "similarity_distribution": {
                "excellent (≥0.7)": sum(1 for s in similarities if s >= 0.7),
                "good (0.5-0.7)": sum(1 for s in similarities if 0.5 <= s < 0.7),
                "fair (0.3-0.5)": sum(1 for s in similarities if 0.3 <= s < 0.5),
                "poor (<0.3)": sum(1 for s in similarities if s < 0.3)
            }
        }


def main():
    """Test improved RAG engine."""
    import os
    
    # Path to chunks
    chunks_path = "/Users/nikolashulewsky/snf-news-aggregator/idaho-alf-chatbot/data/processed/chunks_with_embeddings.json"
    
    if not Path(chunks_path).exists():
        print(f"ERROR: {chunks_path} not found")
        return
    
    print("="*80)
    print("IMPROVED RAG ENGINE TEST")
    print("="*80 + "\n")
    
    # Initialize improved RAG engine
    rag = ImprovedRAGEngine(
        chunks_with_embeddings_path=chunks_path,
        embedding_provider="openai"
    )
    
    # Test questions
    test_questions = [
        "What are the staffing requirements for a 20-bed facility?",
        "How much square footage is required per resident?",
        "What are the bathroom requirements?",
    ]
    
    for question in test_questions:
        print(f"\n{'='*80}")
        print(f"QUESTION: {question}")
        print(f"{'='*80}\n")
        
        # Get retrieval stats
        stats = rag.get_retrieval_stats(question)
        print(f"Retrieval Stats:")
        print(f"  Total chunks: {stats['total_chunks']}")
        print(f"  Avg similarity: {stats['avg_similarity']:.4f}")
        print(f"  Max similarity: {stats['max_similarity']:.4f}")
        print(f"  Min similarity: {stats['min_similarity']:.4f}")
        print(f"\n  Distribution:")
        for key, value in stats['similarity_distribution'].items():
            print(f"    {key}: {value}")
        
        # Get answer
        result = rag.answer_question(
            question,
            top_k=12,
            temperature=0.5,
            verbose=True
        )
        
        print(f"\n{'='*80}")
        print("ANSWER")
        print(f"{'='*80}")
        print(result["response"][:500] + "...")
        print(f"\nCitations: {len(result['citations'])}")
        print(f"Avg similarity: {result['usage']['avg_similarity']:.4f}")


if __name__ == "__main__":
    main()

