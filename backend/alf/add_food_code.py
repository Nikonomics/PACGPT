"""
Add food code chunks to knowledge base.
"""

import json
from pathlib import Path
from embeddings import ChunkEmbeddingManager, create_embedding_generator
import os

def main():
    # Set up paths
    base_dir = Path(__file__).parent.parent
    food_code_file = base_dir / 'data' / 'processed' / 'food_code_chunks.json'
    existing_file = base_dir / 'data' / 'processed' / 'chunks_with_embeddings.json'
    
    # Load food code chunks
    with open(food_code_file, 'r') as f:
        food_code_chunks = json.load(f)
    
    print(f'Loaded {len(food_code_chunks)} food code chunks')
    print('Generating embeddings...\n')
    
    # Generate embeddings
    embedding_generator = create_embedding_generator(
        provider='openai',
        api_key=os.getenv('OPENAI_API_KEY')
    )
    
    food_code_with_embeddings = []
    for i, chunk in enumerate(food_code_chunks):
        print(f'Generating embedding {i+1}/{len(food_code_chunks)}: {chunk["citation"]}')
        embedding = embedding_generator.generate_embedding(chunk['content'])
        chunk['embedding'] = embedding
        food_code_with_embeddings.append(chunk)
    
    print(f'\n✓ Generated embeddings for {len(food_code_with_embeddings)} chunks')
    
    # Load existing chunks
    with open(existing_file, 'r') as f:
        existing_chunks = json.load(f)
    
    print(f'Loaded {len(existing_chunks)} existing chunks')
    
    # Merge
    merged_chunks = existing_chunks + food_code_with_embeddings
    print(f'Total chunks after merge: {len(merged_chunks)}')
    
    # Save
    with open(existing_file, 'w') as f:
        json.dump(merged_chunks, f, indent=2, ensure_ascii=False)
    
    print(f'✓ Saved merged chunks to {existing_file}')
    print(f'\nSummary:')
    print(f'  Existing chunks: {len(existing_chunks)}')
    print(f'  Food code chunks: {len(food_code_with_embeddings)}')
    print(f'  Total chunks: {len(merged_chunks)}')

if __name__ == '__main__':
    main()

