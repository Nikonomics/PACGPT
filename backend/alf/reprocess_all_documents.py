"""
Reprocess all documents from scratch with improved chunking and deduplication.
"""

import json
from pathlib import Path
from txt_processor import IDAPATextProcessor, deduplicate_chunks
from embeddings import create_embedding_generator, ChunkEmbeddingManager
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def main():
    """Reprocess all documents with improved chunking."""

    print("="*80)
    print("REPROCESSING ALL DOCUMENTS WITH IMPROVED CHUNKING")
    print("="*80 + "\n")

    # Set up paths
    base_dir = Path(__file__).parent
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"

    # Create backup of existing chunks
    existing_file = processed_dir / "chunks_with_embeddings.json"
    if existing_file.exists():
        backup_name = f"chunks_with_embeddings_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        backup_file = processed_dir / backup_name
        print(f"Creating backup: {backup_name}")
        with open(existing_file, 'r') as f:
            backup_data = json.load(f)
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f)
        print(f"✓ Backup created with {len(backup_data)} chunks\n")

    # Initialize processor
    processor = IDAPATextProcessor(str(raw_dir), str(processed_dir))

    # Process all text files
    print("Processing all regulation files...\n")
    all_chunks_by_file = processor.process_all_files()

    # Combine all chunks
    all_chunks = []
    for filename, chunks in all_chunks_by_file.items():
        all_chunks.extend(chunks)

    print(f"\nTotal chunks before deduplication: {len(all_chunks)}")

    # Deduplicate
    unique_chunks = deduplicate_chunks(all_chunks)
    print(f"Total chunks after deduplication: {len(unique_chunks)}")
    print(f"Removed {len(all_chunks) - len(unique_chunks)} duplicate chunks\n")

    # Save chunks to file for embedding generation
    chunks_data = [chunk.to_dict() for chunk in unique_chunks]
    chunks_file = processed_dir / "all_chunks.json"
    with open(chunks_file, 'w', encoding='utf-8') as f:
        json.dump(chunks_data, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved {len(chunks_data)} chunks to {chunks_file}\n")

    # Preview some chunks to verify
    print("="*80)
    print("PREVIEW OF CHUNKS")
    print("="*80 + "\n")

    for i, chunk in enumerate(unique_chunks[:5]):
        print(f"{i+1}. Source: {chunk.source_file}")
        print(f"   Citation: {chunk.citation}")
        print(f"   Title: {chunk.section_title}")
        print(f"   Size: {len(chunk.content)} chars")
        print(f"   Part: {chunk.chunk_index + 1}/{chunk.total_chunks}")
        print()

    # Generate embeddings
    print("="*80)
    print("GENERATING EMBEDDINGS")
    print("="*80 + "\n")

    # Initialize embedding generator
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not found in environment")
        return

    embedding_generator = create_embedding_generator(
        provider="openai",
        api_key=api_key
    )

    # Use ChunkEmbeddingManager for batch processing
    manager = ChunkEmbeddingManager(embedding_generator, str(processed_dir))
    output_path = manager.embed_chunks(
        chunks_file="all_chunks.json",
        output_file="chunks_with_embeddings.json",
        batch_size=50  # Smaller batches for reliability
    )

    # Print summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)

    # Load the final output
    with open(output_path, 'r') as f:
        chunks_with_embeddings = json.load(f)

    print(f"Total chunks: {len(chunks_with_embeddings)}")

    # Source file breakdown
    source_counts = {}
    for chunk in chunks_with_embeddings:
        source = chunk.get("source_file", "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1

    print(f"\nChunks by source file:")
    for source, count in sorted(source_counts.items()):
        print(f"  {count:4d}: {source}")

    # Category breakdown
    category_counts = {}
    for chunk in chunks_with_embeddings:
        category = chunk.get("category", "unknown")
        category_counts[category] = category_counts.get(category, 0) + 1

    print(f"\nChunks by category:")
    for category, count in sorted(category_counts.items()):
        print(f"  {count:4d}: {category}")

    # Chunk size statistics
    sizes = [len(chunk.get("content", "")) for chunk in chunks_with_embeddings]
    print(f"\nChunk size statistics:")
    print(f"  Min: {min(sizes)} chars")
    print(f"  Max: {max(sizes)} chars")
    print(f"  Avg: {sum(sizes) // len(sizes)} chars")

    # Multi-part chunks
    multi_part = sum(1 for c in chunks_with_embeddings if c.get("total_chunks", 1) > 1)
    print(f"\nMulti-part chunks: {multi_part}")

    print("\n" + "="*80)
    print("REPROCESSING COMPLETE!")
    print("="*80)
    output_file = Path(output_path)
    print(f"\nOutput file: {output_path}")
    print(f"File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"Total chunks: {len(chunks_with_embeddings)}")


if __name__ == "__main__":
    main()
