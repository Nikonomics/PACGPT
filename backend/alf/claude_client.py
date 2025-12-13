"""
Claude API Client for Idaho ALF RegNavigator
Handles interactions with Claude API for generating responses.
"""

import os
import json
from typing import List, Dict, Optional
import anthropic


class ClaudeClient:
    """Client for interacting with Claude API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514"
    ):
        """
        Initialize Claude client.

        Args:
            api_key: Anthropic API key (if None, reads from ANTHROPIC_API_KEY env var)
            model: Claude model to use
        """
        if api_key is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def create_system_prompt(self, retrieved_chunks: List[Dict]) -> str:
        """
        Create system prompt with regulatory context.

        Args:
            retrieved_chunks: List of relevant regulation chunks

        Returns:
            System prompt string
        """
        context = "\n\n".join([
            f"[{chunk['citation']}] {chunk['section_title']}\n{chunk['content']}"
            for chunk in retrieved_chunks
        ])

        system_prompt = f"""You are a regulatory compliance expert for Idaho assisted living facilities.

Your role:
- Answer questions about Idaho IDAPA 16.03.22 regulations for residential assisted living facilities
- Provide clear, accurate explanations in plain English
- Always cite specific sections (e.g., "According to IDAPA 16.03.22.600...")
- Be precise and accurate - if you're unsure about something, say so
- Never make up information or extrapolate beyond what's in the regulations

Response format:
1. Direct answer to the question
2. Specific citation with detailed explanation from the regulations
3. Practical implications for facility operators
4. Related regulations if relevant

Context from Idaho regulations:
{context}

When answering:
- Quote relevant regulatory language when appropriate
- Explain technical terms in plain English
- Point out important requirements, deadlines, or conditions
- Mention exceptions or special circumstances if they exist
"""

        return system_prompt

    def generate_response(
        self,
        query: str,
        retrieved_chunks: List[Dict],
        conversation_history: Optional[List[Dict]] = None,
        max_tokens: int = 2000,
        temperature: float = 0.3
    ) -> Dict:
        """
        Generate response to user query with regulatory context.

        Args:
            query: User's question
            retrieved_chunks: Relevant regulation chunks from vector search
            conversation_history: Previous conversation messages
            max_tokens: Maximum tokens in response
            temperature: Temperature for response generation (0.0-1.0)

        Returns:
            Dict with response text and metadata
        """
        # Create system prompt with context
        system_prompt = self.create_system_prompt(retrieved_chunks)

        # Build messages
        messages = []

        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)

        # Add current query
        messages.append({
            "role": "user",
            "content": query
        })

        # Call Claude API
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages
            )

            # Extract response
            response_text = response.content[0].text

            # Get citations from retrieved chunks
            citations = [
                {
                    "citation": chunk["citation"],
                    "section_title": chunk["section_title"],
                    "chunk_id": chunk["chunk_id"]
                }
                for chunk in retrieved_chunks
            ]

            return {
                "response": response_text,
                "citations": citations,
                "model": self.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                }
            }

        except Exception as e:
            print(f"Error calling Claude API: {e}")
            raise

    def generate_response_streaming(
        self,
        query: str,
        retrieved_chunks: List[Dict],
        conversation_history: Optional[List[Dict]] = None,
        max_tokens: int = 2000,
        temperature: float = 0.3
    ):
        """
        Generate streaming response to user query.

        Yields response text chunks as they're generated.

        Args:
            query: User's question
            retrieved_chunks: Relevant regulation chunks from vector search
            conversation_history: Previous conversation messages
            max_tokens: Maximum tokens in response
            temperature: Temperature for response generation

        Yields:
            Response text chunks
        """
        # Create system prompt with context
        system_prompt = self.create_system_prompt(retrieved_chunks)

        # Build messages
        messages = []

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({
            "role": "user",
            "content": query
        })

        # Stream response
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=messages
            ) as stream:
                for text in stream.text_stream:
                    yield text

        except Exception as e:
            print(f"Error streaming from Claude API: {e}")
            raise


def main():
    """Test Claude client."""
    import sys

    # Test query
    test_query = "What are the staffing requirements for a 20-bed facility?"

    # Mock retrieved chunks
    mock_chunks = [
        {
            "chunk_id": "idapa_16.03.22_600",
            "citation": "IDAPA 16.03.22.600",
            "section_title": "REQUIREMENTS FOR STAFFING STANDARDS",
            "content": """600. REQUIREMENTS FOR STAFFING STANDARDS.
01. Staffing Standards. A facility must provide twenty-four (24) hour-a-day direct care staff sufficient to
meet the scheduled and unscheduled needs of the residents. (3-15-22)
02. Minimum Staffing. At least one (1) staff member, awake and on duty at all times, must be on the
premises for every sixteen (16) residents, or portion thereof. This does not include the administrator. (3-15-22)
03. Additional Staffing. A facility must provide additional staff above the minimum when needed to
ensure resident safety and meet resident care needs according to the negotiated service agreement. (3-15-22)"""
        }
    ]

    print("="*80)
    print("TESTING CLAUDE CLIENT")
    print("="*80)
    print(f"Query: {test_query}\n")

    try:
        # Create client
        client = ClaudeClient()
        print(f"✓ Claude client initialized (model: {client.model})\n")

        # Generate response
        print("Generating response...\n")
        result = client.generate_response(
            query=test_query,
            retrieved_chunks=mock_chunks
        )

        print("="*80)
        print("RESPONSE")
        print("="*80)
        print(result["response"])

        print("\n" + "="*80)
        print("CITATIONS")
        print("="*80)
        for citation in result["citations"]:
            print(f"- {citation['citation']}: {citation['section_title']}")

        print("\n" + "="*80)
        print("USAGE")
        print("="*80)
        print(f"Input tokens: {result['usage']['input_tokens']}")
        print(f"Output tokens: {result['usage']['output_tokens']}")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
