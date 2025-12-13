"""
Diagnostic script to analyze RAG retrieval quality.
Shows what chunks are being retrieved and their similarity scores.
"""

import json
from pathlib import Path
from rag_engine import RAGEngine
import os
from dotenv import load_dotenv


def main():
    """Diagnose RAG retrieval for sample questions."""
    
    load_dotenv()
    
    # Path to chunks
    chunks_path = Path(__file__).parent.parent / "data" / "processed" / "chunks_with_embeddings.json"
    
    if not chunks_path.exists():
        print(f"ERROR: {chunks_path} not found")
        return
    
    # Initialize RAG engine
    print("Initializing RAG engine...")
    rag = RAGEngine(
        chunks_with_embeddings_path=str(chunks_path),
        embedding_provider="openai"
    )
    
    print(f"✓ Loaded {len(rag.chunks)} chunks\n")
    
    # Test questions
    test_questions = [
        "What are the staffing requirements for a 20-bed facility?",
        "How much square footage is required per resident?",
        "What are the bathroom requirements?",
        "Do I need a sprinkler system?",
        "Can staff assist with insulin?"
    ]
    
    print("="*80)
    print("RAG RETRIEVAL DIAGNOSTIC")
    print("="*80 + "\n")
    
    for question in test_questions:
        print(f"\n{'='*80}")
        print(f"QUESTION: {question}")
        print(f"{'='*80}\n")
        
        # Test with different top_k values
        for top_k in [3, 5, 10]:
            print(f"\n--- Top K = {top_k} ---")
            
            # Retrieve chunks
            results = rag.retrieve_relevant_chunks(question, top_k=top_k, similarity_threshold=0.0)
            
            if not results:
                print("  ❌ No chunks retrieved!")
                continue
            
            print(f"  Retrieved {len(results)} chunks:\n")
            
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
                print(f"     Citation: {chunk['citation']}")
                print(f"     Title: {chunk['section_title']}")
                print(f"     Content length: {len(chunk['content'])} chars")
                print(f"     Preview: {chunk['content'][:150]}...")
                print()
        
        # Test with different similarity thresholds
        print(f"\n--- Similarity Threshold Analysis ---")
        
        for threshold in [0.0, 0.3, 0.5, 0.7]:
            results = rag.retrieve_relevant_chunks(question, top_k=10, similarity_threshold=threshold)
            print(f"  Threshold {threshold:.1f}: {len(results)} chunks retrieved")
        
        print("\n" + "-"*80)
    
    print("\n" + "="*80)
    print("DIAGNOSTIC COMPLETE")
    print("="*80)
    
    # Summary recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    print("""
Based on the diagnostic results:

1. **Increase top_k**: With 225 chunks, try top_k=10 or 15 for better context
2. **Lower similarity threshold**: Try 0.0 to see all relevant chunks, then adjust
3. **Increase content length**: The 1000 char limit might be too restrictive
4. **Check embedding quality**: Make sure all chunks have proper embeddings
5. **Consider reranking**: Add diversity to avoid duplicate/similar chunks

Next steps:
- Run this diagnostic to see actual retrieval performance
- Adjust rag_engine.py settings based on results
- Test with real questions to validate improvements
""")


if __name__ == "__main__":
    main()

