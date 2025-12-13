"""
Reprocess all documents from scratch with correct citations.
"""

import json
from pathlib import Path
from txt_processor import IDAPATextProcessor
from embeddings import ChunkEmbeddingManager, create_embedding_generator
import os


def main():
    """Reprocess all documents with correct citations."""
    
    print("="*80)
    print("REPROCESSING ALL DOCUMENTS WITH CORRECT CITATIONS")
    print("="*80 + "\n")
    
    # Set up paths
    base_dir = Path(__file__).parent.parent
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"
    
    # Initialize processor
    processor = IDAPATextProcessor(str(raw_dir), str(processed_dir))
    
    # Process all text files
    print("Processing all regulation files...\n")
    all_chunks_by_file = processor.process_all_files()
    
    # Combine all chunks
    all_chunks = []
    for filename, chunks in all_chunks_by_file.items():
        all_chunks.extend(chunks)
    
    print(f"\nTotal chunks created: {len(all_chunks)}\n")
    
    # Preview some chunks to verify citations
    print("="*80)
    print("PREVIEW OF CHUNKS (verifying citations)")
    print("="*80 + "\n")
    
    for i, chunk in enumerate(all_chunks[:10]):
        print(f"{i+1}. Source: {chunk.source_file}")
        print(f"   Citation: {chunk.citation}")
        print(f"   Title: {chunk.section_title}")
        print()
    
    # Save chunks without embeddings first
    processor.save_chunks(all_chunks, "all_chunks_reprocessed.json")
    
    # Generate embeddings
    print("="*80)
    print("GENERATING EMBEDDINGS")
    print("="*80 + "\n")
    
    # Initialize embedding generator
    embedding_generator = create_embedding_generator(
        provider="openai",
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    embedding_manager = ChunkEmbeddingManager(
        embedding_generator,
        str(processed_dir)
    )
    
    # Generate embeddings
    chunks_with_embeddings = []
    for i, chunk in enumerate(all_chunks):
        print(f"Generating embedding {i+1}/{len(all_chunks)}: {chunk.citation}")
        chunk_dict = chunk.to_dict()
        
        # Generate embedding
        embedding = embedding_generator.generate_embedding(chunk.content)
        chunk_dict["embedding"] = embedding
        
        chunks_with_embeddings.append(chunk_dict)
    
    print(f"\n✓ Generated embeddings for {len(chunks_with_embeddings)} chunks\n")
    
    # Save chunks with embeddings
    output_file = processed_dir / "chunks_with_embeddings.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(chunks_with_embeddings, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved chunks with embeddings to {output_file}\n")
    
    # Print summary statistics
    print("="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"Total chunks: {len(chunks_with_embeddings)}")
    
    # Citations breakdown
    citations = {}
    for chunk in chunks_with_embeddings:
        citation = chunk['citation']
        if citation not in citations:
            citations[citation] = 0
        citations[citation] += 1
    
    print(f"\nCitations by document:")
    for citation, count in sorted(citations.items()):
        print(f"  {citation}: {count} chunks")
    
    # Category breakdown
    category_counts = {}
    for chunk in chunks_with_embeddings:
        category = chunk.get("category", "unknown")
        category_counts[category] = category_counts.get(category, 0) + 1
    
    print(f"\nChunks by category:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count}")
    
    # Source file breakdown
    source_counts = {}
    for chunk in chunks_with_embeddings:
        source = chunk.get("source_file", "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
    
    print(f"\nChunks by source file:")
    for source, count in sorted(source_counts.items()):
        print(f"  {source}: {count}")
    
    print("\n" + "="*80)
    print("REPROCESSING COMPLETE!")
    print("="*80)
    print(f"\nOutput file: {output_file}")
    print(f"File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"Total chunks: {len(chunks_with_embeddings)}")


if __name__ == "__main__":
    main()

