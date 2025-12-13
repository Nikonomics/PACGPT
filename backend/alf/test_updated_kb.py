"""
Quick test script to verify the updated knowledge base works correctly.
"""

import json
from pathlib import Path
from rag_engine import RAGEngine
import os


def main():
    """Test the updated knowledge base with sample questions."""
    
    print("="*80)
    print("TESTING UPDATED KNOWLEDGE BASE")
    print("="*80 + "\n")
    
    # Load environment variables
    from dotenv import load_dotenv
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
    
    # Test questions that should leverage the new documents
    test_questions = [
        "What are the reportable diseases in Idaho?",
        "What are the food safety requirements?",
        "What are the criminal background check requirements?",
        "What are the building safety requirements?",
        "What are the nursing board requirements?"
    ]
    
    print("="*80)
    print("TESTING WITH SAMPLE QUESTIONS")
    print("="*80 + "\n")
    
    for i, question in enumerate(test_questions, 1):
        print(f"Question {i}: {question}")
        print("-" * 80)
        
        try:
            result = rag.answer_question(
                question,
                top_k=3,
                verbose=False
            )
            
            print(f"Answer: {result['response'][:200]}...")
            print(f"\nCitations: {len(result['citations'])}")
            for citation in result['citations']:
                print(f"  • {citation['citation']}: {citation['section_title']}")
            print()
            
        except Exception as e:
            print(f"ERROR: {e}\n")
    
    print("="*80)
    print("TESTING COMPLETE!")
    print("="*80)


if __name__ == "__main__":
    main()

