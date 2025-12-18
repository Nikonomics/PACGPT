"""
Re-chunk Arizona source files with cleaned versions.
Preserves metadata where possible, generates new embeddings.
"""

import json
import os
import re
from pathlib import Path
from improved_processor import RegulatoryDataPipeline, ChunkConfig

# For embedding generation
from embeddings import create_embedding_generator


def count_mid_sentence_chunks(chunks):
    """Count chunks that end mid-sentence."""
    mid_sentence = 0
    for chunk in chunks:
        content = chunk.get('content', '').strip()
        if content:
            # Get last non-whitespace character
            last_char = content[-1] if content else ''
            # Check if it ends with proper punctuation
            if last_char not in '.!?;:)"]':
                mid_sentence += 1
    return mid_sentence


def main():
    """Re-chunk Arizona files and update the knowledge base."""

    print("="*80)
    print("ARIZONA RE-CHUNKING PIPELINE")
    print("="*80 + "\n")

    # Set up paths
    base_dir = Path(__file__).parent
    raw_dir = base_dir / "data" / "raw"
    processed_dir = base_dir / "data" / "processed"
    chunks_file = processed_dir / "chunks_with_embeddings.json"

    # Files to re-chunk
    az_files_to_rechunk = [
        "AZ article-8.txt",
        "AZ 9-08.txt",
        "AZ 4-33.txt"
    ]

    # Load existing chunks
    print("Loading existing chunks...")
    with open(chunks_file, 'r', encoding='utf-8') as f:
        all_chunks = json.load(f)
    print(f"  Loaded {len(all_chunks)} total chunks")

    # Identify old Arizona chunks from these files
    old_az_chunks = []
    other_chunks = []
    for chunk in all_chunks:
        source = chunk.get('source_file', chunk.get('source_document', ''))
        if source in az_files_to_rechunk:
            old_az_chunks.append(chunk)
        else:
            other_chunks.append(chunk)

    print(f"  Found {len(old_az_chunks)} old chunks from target files")
    print(f"  Keeping {len(other_chunks)} chunks from other files")

    # Count mid-sentence in old chunks
    old_mid_sentence = count_mid_sentence_chunks(old_az_chunks)
    print(f"  Old mid-sentence ending rate: {old_mid_sentence}/{len(old_az_chunks)} ({100*old_mid_sentence/len(old_az_chunks) if old_az_chunks else 0:.1f}%)")

    # Extract metadata from old chunks for reference
    old_metadata_by_section = {}
    for chunk in old_az_chunks:
        section = chunk.get('section_number', '')
        if section and section not in old_metadata_by_section:
            old_metadata_by_section[section] = {
                'citations': chunk.get('citations', []),
                'topic_tags': chunk.get('topic_tags', []),
                'facility_types': chunk.get('facility_types', []),
            }

    print(f"\n{'='*80}")
    print("PROCESSING FILES")
    print("="*80 + "\n")

    # Initialize processor
    pipeline = RegulatoryDataPipeline()

    # Process each file
    new_chunks = []
    for filename in az_files_to_rechunk:
        file_path = raw_dir / filename
        print(f"Processing: {filename}")

        if not file_path.exists():
            print(f"  ERROR: File not found: {file_path}")
            continue

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Process through improved pipeline
        chunks = pipeline.process_document(content, filename)

        # Convert Chunk objects to dicts and enrich with Arizona metadata
        for chunk in chunks:
            chunk_dict = chunk.to_dict()

            # Set Arizona jurisdiction
            chunk_dict['jurisdiction'] = 'Arizona'
            chunk_dict['source_file'] = filename
            chunk_dict['source_document'] = filename

            # Try to carry forward metadata from old chunks
            section = chunk_dict.get('section_number', '')
            if section in old_metadata_by_section:
                old_meta = old_metadata_by_section[section]
                # Carry forward citations if we have them
                if old_meta.get('citations'):
                    chunk_dict['citations'] = old_meta['citations']
                # Merge topic tags
                if old_meta.get('topic_tags'):
                    existing_tags = set(chunk_dict.get('topic_tags', []))
                    existing_tags.update(old_meta['topic_tags'])
                    chunk_dict['topic_tags'] = list(existing_tags)
                # Carry forward facility types
                if old_meta.get('facility_types'):
                    chunk_dict['facility_types'] = old_meta['facility_types']

            # Extract citations from content if not already present
            if not chunk_dict.get('citations'):
                chunk_dict['citations'] = extract_az_citations(chunk_dict.get('content', ''))

            new_chunks.append(chunk_dict)

        print(f"  Created {len(chunks)} chunks")

    print(f"\nTotal new chunks: {len(new_chunks)}")

    # Count mid-sentence in new chunks
    new_mid_sentence = count_mid_sentence_chunks(new_chunks)
    print(f"New mid-sentence ending rate: {new_mid_sentence}/{len(new_chunks)} ({100*new_mid_sentence/len(new_chunks) if new_chunks else 0:.1f}%)")

    print(f"\n{'='*80}")
    print("GENERATING EMBEDDINGS")
    print("="*80 + "\n")

    # Initialize embedding generator
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: OPENAI_API_KEY not set")
        return

    embedding_generator = create_embedding_generator(
        provider="openai",
        api_key=api_key
    )

    # Generate embeddings in batches
    batch_size = 20
    for i in range(0, len(new_chunks), batch_size):
        batch = new_chunks[i:i+batch_size]
        batch_texts = [c['content'] for c in batch]

        print(f"  Generating embeddings {i+1}-{min(i+batch_size, len(new_chunks))} of {len(new_chunks)}...")
        embeddings = embedding_generator.generate_embeddings(batch_texts)

        for j, embedding in enumerate(embeddings):
            new_chunks[i+j]['embedding'] = embedding

    print(f"\n  Generated embeddings for {len(new_chunks)} chunks")

    print(f"\n{'='*80}")
    print("UPDATING KNOWLEDGE BASE")
    print("="*80 + "\n")

    # Combine other chunks with new Arizona chunks
    merged_chunks = other_chunks + new_chunks
    print(f"Total chunks after merge: {len(merged_chunks)}")

    # Save updated chunks
    backup_file = processed_dir / "chunks_with_embeddings.json.bak"
    print(f"\nBacking up to {backup_file}...")
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    print(f"Saving to {chunks_file}...")
    with open(chunks_file, 'w', encoding='utf-8') as f:
        json.dump(merged_chunks, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*80}")
    print("SUMMARY")
    print("="*80)
    print(f"\nBEFORE:")
    print(f"  Chunks from target files: {len(old_az_chunks)}")
    print(f"  Mid-sentence endings: {old_mid_sentence} ({100*old_mid_sentence/len(old_az_chunks) if old_az_chunks else 0:.1f}%)")

    print(f"\nAFTER:")
    print(f"  Chunks from target files: {len(new_chunks)}")
    print(f"  Mid-sentence endings: {new_mid_sentence} ({100*new_mid_sentence/len(new_chunks) if new_chunks else 0:.1f}%)")

    print(f"\nIMPROVEMENT:")
    if old_az_chunks and new_chunks:
        old_rate = 100*old_mid_sentence/len(old_az_chunks)
        new_rate = 100*new_mid_sentence/len(new_chunks)
        print(f"  Mid-sentence rate: {old_rate:.1f}% -> {new_rate:.1f}%")

    # Breakdown by file
    print("\nChunks by file:")
    file_counts = {}
    for chunk in new_chunks:
        source = chunk.get('source_file', 'unknown')
        file_counts[source] = file_counts.get(source, 0) + 1
    for source, count in sorted(file_counts.items()):
        print(f"  {source}: {count}")

    print("\n" + "="*80)
    print("DONE!")
    print("="*80)


def extract_az_citations(content: str) -> list:
    """Extract Arizona citations from content."""
    citations = []

    # AAC format: R9-10-801
    aac_matches = re.findall(r'R(\d+-\d+-\d+)', content)
    for match in aac_matches:
        citations.append(f"R{match}")

    # ARS format: 36-401, 36-446.04
    ars_matches = re.findall(r'(\d{2}-\d{3,4}(?:\.\d{2})?)', content)
    for match in ars_matches:
        citations.append(f"A.R.S. {match}")

    # Deduplicate
    return list(dict.fromkeys(citations))


if __name__ == "__main__":
    main()
