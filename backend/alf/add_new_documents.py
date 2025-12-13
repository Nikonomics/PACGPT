"""
Script to add new regulation documents to the Idaho ALF knowledge base.
Processes new text files, generates embeddings, and merges with existing chunks.
"""

import json
from pathlib import Path
from txt_processor import IDAPATextProcessor
from embeddings import ChunkEmbeddingManager, create_embedding_generator
import os


def main():
    """Main pipeline to add new documents to knowledge base."""
    
    print("="*80)
    print("IDAHO ALF KNOWLEDGE BASE - ADD NEW DOCUMENTS")
    print("="*80 + "\n")
    
    # Set up paths
    base_dir = Path(__file__).parent.parent
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"
    
    # Existing chunks file
    existing_chunks_file = processed_dir / "chunks_with_embeddings.json"
    
    # New files to process (excluding already processed ones)
    new_files = [
        "IDAPA 16.02.1 idaho reportable diseases.txt",
        "IDAPA 16.02.19 food code.txt",
        "IDAPA 16.05.01 use and disclosure of department records.txt",
        "IDAPA 16.05.06 criminal history background checks.txt",
        "IDAPA 24.34.01 idaho board of nursing.txt",
        "IDAPA 24.39.30 rules of building safety.txt",
        "US Public Health Food Code.txt",
        "ADA Accessibility Guidelines for Buildings and Facilities.txt",
        "Title 74 Transparent and Ethical Government - Chapter 1 Public Records Act.txt"
    ]
    
    print(f"Processing {len(new_files)} new regulation files...\n")
    
    # Initialize processor
    processor = IDAPATextProcessor(str(raw_dir), str(processed_dir))
    
    # Process new files
    all_new_chunks = []
    for filename in new_files:
        file_path = raw_dir / filename
        if file_path.exists():
            print(f"Processing: {filename}")
            chunks = processor.process_file(filename)
            all_new_chunks.extend(chunks)
            print(f"  ✓ Created {len(chunks)} chunks\n")
        else:
            print(f"  ⚠ File not found: {filename}\n")
    
    if not all_new_chunks:
        print("No new chunks to process. Exiting.")
        return
    
    print(f"Total new chunks created: {len(all_new_chunks)}\n")
    
    # Preview some chunks
    print("="*80)
    print("PREVIEW OF NEW CHUNKS")
    print("="*80 + "\n")
    for i, chunk in enumerate(all_new_chunks[:3]):
        print(f"Chunk {i+1}:")
        print(f"  ID: {chunk.chunk_id}")
        print(f"  Citation: {chunk.citation}")
        print(f"  Title: {chunk.section_title}")
        print(f"  Category: {chunk.category}")
        print(f"  Content length: {len(chunk.content)} chars")
        print(f"  Content preview: {chunk.content[:150]}...")
        print()
    
    # Save new chunks to separate file
    new_chunks_file = processed_dir / "new_chunks.json"
    processor.save_chunks(all_new_chunks, "new_chunks.json")
    
    # Generate embeddings for new chunks
    print("="*80)
    print("GENERATING EMBEDDINGS FOR NEW CHUNKS")
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
    new_chunks_with_embeddings = []
    for i, chunk in enumerate(all_new_chunks):
        print(f"Generating embedding {i+1}/{len(all_new_chunks)}: {chunk.citation}")
        chunk_dict = chunk.to_dict()
        
        # Generate embedding
        embedding = embedding_generator.generate_embedding(chunk.content)
        chunk_dict["embedding"] = embedding
        
        new_chunks_with_embeddings.append(chunk_dict)
    
    print(f"\n✓ Generated embeddings for {len(new_chunks_with_embeddings)} chunks\n")
    
    # Save new chunks with embeddings
    new_chunks_emb_file = processed_dir / "new_chunks_with_embeddings.json"
    with open(new_chunks_emb_file, 'w', encoding='utf-8') as f:
        json.dump(new_chunks_with_embeddings, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved new chunks with embeddings to {new_chunks_emb_file}\n")
    
    # Load existing chunks
    print("="*80)
    print("MERGING WITH EXISTING KNOWLEDGE BASE")
    print("="*80 + "\n")
    
    if existing_chunks_file.exists():
        with open(existing_chunks_file, 'r', encoding='utf-8') as f:
            existing_chunks = json.load(f)
        print(f"Loaded {len(existing_chunks)} existing chunks")
    else:
        existing_chunks = []
        print("No existing chunks file found, starting fresh")
    
    # Merge chunks
    merged_chunks = existing_chunks + new_chunks_with_embeddings
    print(f"Total chunks after merge: {len(merged_chunks)}\n")
    
    # Save merged chunks
    with open(existing_chunks_file, 'w', encoding='utf-8') as f:
        json.dump(merged_chunks, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved merged chunks to {existing_chunks_file}")
    
    # Print summary statistics
    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"New chunks added: {len(new_chunks_with_embeddings)}")
    print(f"Existing chunks: {len(existing_chunks)}")
    print(f"Total chunks in knowledge base: {len(merged_chunks)}")
    
    # Category breakdown for new chunks
    category_counts = {}
    for chunk in new_chunks_with_embeddings:
        category = chunk.get("category", "unknown")
        category_counts[category] = category_counts.get(category, 0) + 1
    
    print("\nNew chunks by category:")
    for category, count in sorted(category_counts.items()):
        print(f"  {category}: {count}")
    
    # Source file breakdown
    source_counts = {}
    for chunk in new_chunks_with_embeddings:
        source = chunk.get("source_file", "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
    
    print("\nNew chunks by source file:")
    for source, count in sorted(source_counts.items()):
        print(f"  {source}: {count}")
    
    print("\n" + "="*80)
    print("PROCESSING COMPLETE!")
    print("="*80)
    print("\nNext steps:")
    print("1. Review the merged chunks in chunks_with_embeddings.json")
    print("2. Test the updated knowledge base with sample questions")
    print("3. Redeploy the backend to Render if needed")
    print()


if __name__ == "__main__":
    main()

