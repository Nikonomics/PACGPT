"""
Embeddings module for Idaho ALF RegNavigator
Generates and manages vector embeddings for regulatory chunks.
Supports both Voyage AI and OpenAI embeddings.
"""

import os
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
import requests


class EmbeddingGenerator:
    """Base class for embedding generation."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        raise NotImplementedError

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        raise NotImplementedError


class VoyageEmbedding(EmbeddingGenerator):
    """Voyage AI embedding generator."""

    def __init__(self, api_key: str, model: str = "voyage-large-2-instruct"):
        super().__init__(api_key)
        self.model = model
        self.api_url = "https://api.voyageai.com/v1/embeddings"

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using Voyage AI API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "input": texts,
            "model": self.model
        }

        response = requests.post(self.api_url, headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()
        embeddings = [item["embedding"] for item in result["data"]]

        return embeddings

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        return self.generate_embeddings([text])[0]


class OpenAIEmbedding(EmbeddingGenerator):
    """OpenAI embedding generator."""

    def __init__(self, api_key: str, model: str = "text-embedding-3-large"):
        super().__init__(api_key)
        self.model = model
        self.api_url = "https://api.openai.com/v1/embeddings"

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using OpenAI API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "input": texts,
            "model": self.model
        }

        response = requests.post(self.api_url, headers=headers, json=payload)
        response.raise_for_status()

        result = response.json()
        embeddings = [item["embedding"] for item in result["data"]]

        return embeddings

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        return self.generate_embeddings([text])[0]


class ChunkEmbeddingManager:
    """Manages embeddings for regulation chunks."""

    def __init__(
        self,
        embedding_generator: EmbeddingGenerator,
        processed_data_dir: str
    ):
        self.embedding_generator = embedding_generator
        self.processed_data_dir = Path(processed_data_dir)

    def embed_chunks(
        self,
        chunks_file: str = "all_chunks.json",
        output_file: str = "chunks_with_embeddings.json",
        batch_size: int = 100
    ) -> str:
        """
        Generate embeddings for all chunks and save to file.

        Args:
            chunks_file: Input JSON file with chunks
            output_file: Output JSON file with chunks + embeddings
            batch_size: Number of chunks to embed at once

        Returns:
            Path to output file
        """
        chunks_path = self.processed_data_dir / chunks_file
        output_path = self.processed_data_dir / output_file

        # Load chunks
        print(f"Loading chunks from {chunks_path}...")
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        print(f"Loaded {len(chunks)} chunks")

        # Generate embeddings in batches
        print("Generating embeddings...")
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_texts = [chunk["content"] for chunk in batch]

            print(f"  Processing batch {i // batch_size + 1} ({i+1}-{min(i+batch_size, len(chunks))} of {len(chunks)})")

            try:
                embeddings = self.embedding_generator.generate_embeddings(batch_texts)

                # Add embeddings to chunks
                for j, embedding in enumerate(embeddings):
                    chunks[i + j]["embedding"] = embedding
                    chunks[i + j]["embedding_model"] = getattr(
                        self.embedding_generator,
                        'model',
                        'unknown'
                    )

            except Exception as e:
                print(f"  ERROR in batch {i // batch_size + 1}: {e}")
                raise

        # Save chunks with embeddings
        print(f"Saving chunks with embeddings to {output_path}...")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)

        print(f"✓ Successfully generated embeddings for {len(chunks)} chunks")

        # Print statistics
        embedding_dims = len(chunks[0]["embedding"]) if chunks else 0
        print(f"  Embedding dimensions: {embedding_dims}")
        print(f"  File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")

        return str(output_path)

    def compute_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

    def search_similar_chunks(
        self,
        query: str,
        chunks_with_embeddings_file: str = "chunks_with_embeddings.json",
        top_k: int = 5
    ) -> List[Dict]:
        """
        Search for most similar chunks to a query.

        Args:
            query: Search query text
            chunks_with_embeddings_file: File with chunks and embeddings
            top_k: Number of top results to return

        Returns:
            List of top matching chunks with similarity scores
        """
        # Load chunks with embeddings
        chunks_path = self.processed_data_dir / chunks_with_embeddings_file
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)

        # Generate query embedding
        query_embedding = self.embedding_generator.generate_embedding(query)

        # Compute similarities
        similarities = []
        for chunk in chunks:
            if "embedding" not in chunk:
                continue

            similarity = self.compute_similarity(query_embedding, chunk["embedding"])
            similarities.append({
                "chunk": chunk,
                "similarity": similarity
            })

        # Sort by similarity and return top k
        similarities.sort(key=lambda x: x["similarity"], reverse=True)

        return similarities[:top_k]


def create_embedding_generator(
    provider: str = "voyage",
    api_key: Optional[str] = None
) -> EmbeddingGenerator:
    """
    Factory function to create embedding generator.

    Args:
        provider: "voyage" or "openai"
        api_key: API key (if None, reads from environment)

    Returns:
        EmbeddingGenerator instance
    """
    if provider.lower() == "voyage":
        if api_key is None:
            api_key = os.getenv("VOYAGE_API_KEY")
        if not api_key:
            raise ValueError("VOYAGE_API_KEY not found in environment")
        return VoyageEmbedding(api_key)

    elif provider.lower() == "openai":
        if api_key is None:
            api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")
        return OpenAIEmbedding(api_key)

    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'voyage' or 'openai'")


def main():
    """Main function to generate embeddings for chunks."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate embeddings for regulation chunks")
    parser.add_argument(
        "--provider",
        choices=["voyage", "openai"],
        default="openai",
        help="Embedding provider (default: openai)"
    )
    parser.add_argument(
        "--data-dir",
        default="/Users/nikolashulewsky/snf-news-aggregator/idaho-alf-chatbot/data/processed",
        help="Directory with processed chunks"
    )
    parser.add_argument(
        "--chunks-file",
        default="all_chunks.json",
        help="Input chunks file"
    )
    parser.add_argument(
        "--output-file",
        default="chunks_with_embeddings.json",
        help="Output file with embeddings"
    )

    args = parser.parse_args()

    print("="*80)
    print("IDAHO ALF REGULATIONS - EMBEDDING GENERATION")
    print("="*80)
    print(f"Provider: {args.provider}")
    print(f"Data directory: {args.data_dir}")
    print(f"Input file: {args.chunks_file}")
    print(f"Output file: {args.output_file}")
    print("="*80 + "\n")

    # Create embedding generator
    embedding_gen = create_embedding_generator(provider=args.provider)

    # Create manager
    manager = ChunkEmbeddingManager(embedding_gen, args.data_dir)

    # Generate embeddings
    output_path = manager.embed_chunks(
        chunks_file=args.chunks_file,
        output_file=args.output_file
    )

    print("\n" + "="*80)
    print("EMBEDDING GENERATION COMPLETE!")
    print("="*80)
    print(f"Output file: {output_path}")

    # Test search
    print("\n" + "="*80)
    print("TESTING SEARCH")
    print("="*80)

    test_query = "What are the staffing requirements for a 20-bed facility?"
    print(f"\nQuery: {test_query}")
    print("\nTop 3 matches:")

    results = manager.search_similar_chunks(
        test_query,
        chunks_with_embeddings_file=args.output_file,
        top_k=3
    )

    for i, result in enumerate(results, 1):
        chunk = result["chunk"]
        similarity = result["similarity"]
        print(f"\n{i}. {chunk['citation']} - {chunk['section_title']}")
        print(f"   Similarity: {similarity:.4f}")
        print(f"   Preview: {chunk['content'][:150]}...")


if __name__ == "__main__":
    main()
