"""
FastAPI application for Idaho ALF RegNavigator chatbot.
"""

import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

from rag_engine import RAGEngine

# Initialize FastAPI app
app = FastAPI(
    title="Idaho ALF RegNavigator API",
    description="AI-powered chatbot for Idaho assisted living facility regulations",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG engine
CHUNKS_PATH = Path(__file__).parent / "data" / "processed" / "chunks_with_embeddings.json"

rag_engine = None


@app.on_event("startup")
async def startup_event():
    """Initialize RAG engine on startup."""
    global rag_engine

    print("Initializing Idaho ALF RegNavigator...")

    if not CHUNKS_PATH.exists():
        raise RuntimeError(f"Chunks file not found: {CHUNKS_PATH}")

    rag_engine = RAGEngine(
        chunks_with_embeddings_path=str(CHUNKS_PATH),
        embedding_provider="openai",
        claude_model="claude-sonnet-4-20250514"
    )

    print("✓ RAG engine initialized successfully")


# Request/Response models
class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class QueryRequest(BaseModel):
    question: str
    conversation_history: Optional[List[Message]] = None
    top_k: int = 12  # Increased from 5 for better context
    temperature: float = 0.5  # Increased from 0.3 for more natural responses


class Citation(BaseModel):
    citation: str
    section_title: str
    chunk_id: str


class RetrievedChunk(BaseModel):
    citation: str
    section_title: str
    chunk_id: str
    similarity: float
    content: str


class QueryResponse(BaseModel):
    response: str
    citations: List[Citation]
    retrieved_chunks: List[RetrievedChunk]
    usage: dict


class HealthResponse(BaseModel):
    status: str
    message: str
    chunks_loaded: int


# Routes
@app.get("/", response_model=dict)
async def root():
    """Root endpoint."""
    return {
        "message": "Idaho ALF RegNavigator API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG engine not initialized")

    return HealthResponse(
        status="healthy",
        message="RAG engine is running",
        chunks_loaded=len(rag_engine.chunks)
    )


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """
    Answer a question about Idaho ALF regulations.

    Args:
        request: QueryRequest with question and optional conversation history

    Returns:
        QueryResponse with answer, citations, and retrieved chunks
    """
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG engine not initialized")

    try:
        # Convert Pydantic models to dicts for conversation history
        conversation_history = None
        if request.conversation_history:
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]

        # Get answer from RAG engine
        result = rag_engine.answer_question(
            question=request.question,
            conversation_history=conversation_history,
            top_k=request.top_k,
            temperature=request.temperature,
            verbose=False
        )

        # Format response
        return QueryResponse(
            response=result["response"],
            citations=[
                Citation(**citation) for citation in result["citations"]
            ],
            retrieved_chunks=[
                RetrievedChunk(
                    citation=chunk["citation"],
                    section_title=chunk["section_title"],
                    chunk_id=chunk["chunk_id"],
                    similarity=chunk["similarity"],
                    content=chunk["content"][:500] + "..."  # Truncate for response size
                )
                for chunk in result["retrieved_chunks"]
            ],
            usage=result["usage"]
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/chunks", response_model=dict)
async def list_chunks():
    """List all available regulation chunks."""
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG engine not initialized")

    chunks_summary = [
        {
            "chunk_id": chunk["chunk_id"],
            "citation": chunk["citation"],
            "section_title": chunk["section_title"],
            "category": chunk["category"],
            "content": chunk["content"],
            "content_length": len(chunk["content"]),
            "effective_date": chunk.get("effective_date", "2022-03-15"),
            "source_pdf_page": chunk.get("source_pdf_page", 1)
        }
        for chunk in rag_engine.chunks
    ]

    return {
        "total_chunks": len(chunks_summary),
        "chunks": chunks_summary
    }


@app.get("/categories", response_model=dict)
async def list_categories():
    """List all regulation categories."""
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG engine not initialized")

    categories = {}
    for chunk in rag_engine.chunks:
        category = chunk["category"]
        if category not in categories:
            categories[category] = 0
        categories[category] += 1

    return {
        "total_categories": len(categories),
        "categories": categories
    }


if __name__ == "__main__":
    import uvicorn

    # Get port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))

    print("="*80)
    print("IDAHO ALF REGNAVIGATOR API")
    print("="*80)
    print(f"Starting server on http://localhost:{port}")
    print(f"API docs: http://localhost:{port}/docs")
    print("="*80 + "\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True
    )
