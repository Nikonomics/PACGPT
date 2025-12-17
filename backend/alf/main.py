"""
FastAPI application for Idaho ALF RegNavigator chatbot.
"""

import os
import time
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pathlib import Path

from rag_engine import RAGEngine
from analytics import analytics


def get_citation(chunk: dict) -> str:
    """Get citation from chunk, handling both old and new field names."""
    return chunk.get('citation') or chunk.get('section_number', 'N/A')


def get_source(chunk: dict) -> str:
    """Get source document from chunk, handling both old and new field names."""
    return chunk.get('source_file') or chunk.get('source_document', 'N/A')


def get_real_ip(request: Request) -> str:
    """Get real client IP, handling reverse proxies like Render."""
    # X-Forwarded-For contains the real IP when behind a proxy
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # Can be comma-separated list, first one is the real client
        return forwarded_for.split(",")[0].strip()
    # Fall back to direct client IP
    return request.client.host if request.client else None


# Initialize FastAPI app
app = FastAPI(
    title="Idaho ALF RegNavigator API",
    description="AI-powered chatbot for Idaho assisted living facility regulations",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4005",
        "http://localhost:3000",
        "https://postacutegpt.com",
        "https://www.postacutegpt.com",
        "https://senior-chatbots-frontend.onrender.com",
    ],
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
    session_id: Optional[str] = None  # For analytics tracking
    state: Optional[str] = "Idaho"  # State filter for jurisdiction-specific queries


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
async def query(request: QueryRequest, req: Request):
    """
    Answer a question about ALF regulations for a specific state.

    Args:
        request: QueryRequest with question, optional conversation history, and state

    Returns:
        QueryResponse with answer, citations, and retrieved chunks
    """
    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG engine not initialized")

    # Start timing for analytics
    start_time = time.time()

    try:
        # Convert Pydantic models to dicts for conversation history
        conversation_history = None
        if request.conversation_history:
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]

        # Get answer from RAG engine with state filter
        result = rag_engine.answer_question(
            question=request.question,
            conversation_history=conversation_history,
            top_k=request.top_k,
            temperature=request.temperature,
            verbose=False,
            state=request.state  # Pass state for jurisdiction filtering
        )

        # Calculate response time
        response_time_ms = int((time.time() - start_time) * 1000)

        # Log query to analytics
        top_citation = result["citations"][0]["citation"] if result["citations"] else None
        analytics.log_query(
            question=request.question,
            session_id=request.session_id,
            response_time_ms=response_time_ms,
            citations_count=len(result["citations"]),
            top_citation=top_citation,
            ip_address=get_real_ip(req)
        )

        # Format response
        return QueryResponse(
            response=result["response"],
            citations=[
                Citation(**citation) for citation in result["citations"]
            ],
            retrieved_chunks=[
                RetrievedChunk(
                    citation=chunk.get("citation") or chunk.get("section_number", "N/A"),
                    section_title=chunk.get("section_title", "N/A"),
                    chunk_id=chunk.get("chunk_id", "N/A"),
                    similarity=chunk.get("similarity", 0.0),
                    content=chunk.get("content", "")[:500] + "..."  # Truncate for response size
                )
                for chunk in result.get("retrieved_chunks", [])
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
            "chunk_id": chunk.get("chunk_id", "N/A"),
            "citation": get_citation(chunk),
            "section_title": chunk.get("section_title", "N/A"),
            "category": chunk.get("category", "general"),
            "content": chunk.get("content", ""),
            "content_length": len(chunk.get("content", "")),
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
        category = chunk.get("category", "general")
        if category not in categories:
            categories[category] = 0
        categories[category] += 1

    return {
        "total_categories": len(categories),
        "categories": categories
    }


@app.get("/library", response_model=dict)
async def get_library():
    """
    Get hierarchically organized regulation library.
    Returns a tree structure organized by jurisdiction, then by document.
    """
    import re
    from collections import defaultdict

    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG engine not initialized")

    # Jurisdiction display names and order
    jurisdiction_info = {
        'All': {'name': 'Federal Regulations', 'order': 0, 'icon': '🇺🇸'},
        'Idaho': {'name': 'Idaho', 'order': 1, 'icon': '🥔'},
        'Washington': {'name': 'Washington', 'order': 2, 'icon': '🌲'},
        'Oregon': {'name': 'Oregon', 'order': 3, 'icon': '🦫'},
    }

    # Helper to get a clean document name
    def get_doc_display_name(source):
        source_upper = source.upper()

        # Federal documents
        if 'ADA' in source_upper or 'ACCESSIBILITY' in source_upper:
            return 'ADA Accessibility Guidelines'
        elif 'PUBLIC HEALTH FOOD CODE' in source_upper or ('FOOD CODE' in source_upper and 'IDAPA' not in source_upper and 'OR ' not in source_upper):
            return 'FDA Food Code'

        # Idaho documents
        elif 'IDAPA 16.03.22' in source_upper or source_upper == 'IDAPA 16.TXT':
            return 'IDAPA 16.03.22 - Residential Care Facilities'
        elif 'IDAPA 16.02.19' in source_upper:
            return 'IDAPA 16.02.19 - Food Code'
        elif 'IDAPA 16.02.10' in source_upper:
            return 'IDAPA 16.02.10 - Reportable Diseases'
        elif 'IDAPA 16.05.01' in source_upper:
            return 'IDAPA 16.05.01 - Department Records'
        elif 'IDAPA 16.05.06' in source_upper:
            return 'IDAPA 16.05.06 - Background Checks'
        elif 'IDAPA 24.34' in source_upper:
            return 'IDAPA 24.34.01 - Board of Nursing'
        elif 'IDAPA 24.39' in source_upper:
            return 'IDAPA 24.39.30 - Building Safety'
        elif 'TITLE 39' in source_upper:
            return 'Idaho Code Title 39 - ALF Act'
        elif 'TITLE 74' in source_upper:
            return 'Idaho Code Title 74 - Public Records'

        # Washington documents
        elif 'WA CHAPTER 388-78A' in source_upper or '388-78A' in source_upper:
            return 'WAC 388-78A - ALF Licensing'
        elif 'WA CHAPTER 388-112A' in source_upper or '388-112A' in source_upper:
            return 'WAC 388-112A - Training Requirements'
        elif 'WA CHAPTER 246-338' in source_upper:
            return 'WAC 246-338 - Medical Test Sites'
        elif 'WA WAC 246-840-910' in source_upper:
            return 'WAC 246-840-910 - RN Delegation'
        elif 'WA WAC 296-128' in source_upper:
            return 'WAC 296-128 - Sleep Time Rules'
        elif 'WA CHAPTER 18.20 RCW' in source_upper:
            return 'RCW 18.20 - ALF Enabling Statute'
        elif 'WA CHAPTER 70.129 RCW' in source_upper:
            return 'RCW 70.129 - Resident Rights'
        elif 'WA CHAPTER 74.34 RCW' in source_upper:
            return 'RCW 74.34 - Vulnerable Adults'
        elif 'WA TITLE 246' in source_upper:
            return 'WAC Title 246 - Health Rules'

        # Oregon documents
        elif 'OR 411-054' in source_upper:
            return 'OAR 411-054 - ALF Licensing'
        elif 'OR OREGON SECRETARY' in source_upper and 'HUMAN' not in source_upper:
            return 'OAR 411-057 - Memory Care'
        elif 'OR HUMAN SERVICES' in source_upper:
            return 'OAR 407-007 - Background Checks'
        elif 'OR SLEEP' in source_upper:
            return 'OAR 839-020 - Sleep Time Rules'
        elif 'OR FOODSANITATION' in source_upper:
            return 'Oregon Food Sanitation Rules'
        elif 'OR ORS443' in source_upper:
            return 'ORS 443 - Residential Care'
        elif 'OR ORS678' in source_upper:
            return 'ORS 678 - Nursing & Administrators'

        else:
            # Use source filename as fallback
            return source.replace('.txt', '').replace('.TXT', '')

    # Step 1: Group chunks by jurisdiction
    jurisdiction_groups = defaultdict(lambda: defaultdict(list))
    for chunk in rag_engine.chunks:
        jurisdiction = chunk.get('jurisdiction', 'Other')
        source = get_source(chunk)
        doc_name = get_doc_display_name(source)
        jurisdiction_groups[jurisdiction][doc_name].append(chunk)

    # Step 2: Build library tree organized by jurisdiction
    library = []

    for jurisdiction in sorted(jurisdiction_groups.keys(),
                               key=lambda x: jurisdiction_info.get(x, {'order': 99})['order']):
        info = jurisdiction_info.get(jurisdiction, {'name': jurisdiction, 'order': 99, 'icon': '📄'})
        doc_groups = jurisdiction_groups[jurisdiction]

        # Calculate total chunks for this jurisdiction
        total_jurisdiction_chunks = sum(len(chunks) for chunks in doc_groups.values())

        jurisdiction_node = {
            'id': f'jurisdiction-{jurisdiction.lower()}',
            'name': f"{info['icon']} {info['name']}",
            'type': 'jurisdiction',
            'count': total_jurisdiction_chunks,
            'children': []
        }

        # Add documents within this jurisdiction
        for doc_name in sorted(doc_groups.keys()):
            chunks = doc_groups[doc_name]
            doc_id = doc_name.lower().replace(' ', '-').replace('.', '-')

            doc_node = {
                'id': f'{jurisdiction.lower()}-{doc_id}',
                'name': doc_name,
                'type': 'document',
                'count': len(chunks),
                'children': []
            }

            # Group chunks by section (simplified - just show sections)
            section_groups = defaultdict(list)
            for c in chunks:
                section_title = c.get('section_title', '')[:60] or get_citation(c)
                section_groups[section_title].append(c)

            # Add sections (limit to first 30 for performance)
            for section_title in list(section_groups.keys())[:30]:
                section_chunks = section_groups[section_title]
                doc_node['children'].append({
                    'id': section_chunks[0].get('chunk_id', f'{doc_id}-section'),
                    'name': section_title,
                    'type': 'section',
                    'count': len(section_chunks),
                    'chunks': [{'chunk_id': c['chunk_id'], 'citation': get_citation(c),
                               'title': c.get('section_title', '')[:60]} for c in section_chunks[:10]]
                })

            # If there are more sections, add a "more" indicator
            if len(section_groups) > 30:
                doc_node['children'].append({
                    'id': f'{doc_id}-more',
                    'name': f'... and {len(section_groups) - 30} more sections',
                    'type': 'more',
                    'count': len(section_groups) - 30,
                    'chunks': []
                })

            jurisdiction_node['children'].append(doc_node)

        library.append(jurisdiction_node)

    return {
        'total_documents': sum(len(jg) for jg in jurisdiction_groups.values()),
        'total_chunks': len(rag_engine.chunks),
        'library': library
    }


# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================

@app.get("/admin/queries", response_model=dict)
async def get_queries(limit: int = 100, days: int = 30):
    """
    Get recent queries for analytics.

    Args:
        limit: Maximum number of queries to return
        days: Number of days to look back
    """
    queries = analytics.get_recent_queries(limit=limit, days=days)
    return {
        "total": len(queries),
        "queries": queries
    }


@app.get("/admin/popular", response_model=dict)
async def get_popular_queries(limit: int = 20, days: int = 30):
    """
    Get most popular/common queries.

    Args:
        limit: Maximum number of queries to return
        days: Number of days to look back
    """
    popular = analytics.get_popular_queries(limit=limit, days=days)
    return {
        "total": len(popular),
        "queries": popular
    }


@app.get("/admin/stats", response_model=dict)
async def get_stats(days: int = 30):
    """
    Get analytics summary statistics.

    Args:
        days: Number of days to include in stats
    """
    return analytics.get_stats(days=days)


@app.get("/admin/sessions", response_model=dict)
async def get_sessions(days: int = 30, limit: int = 100):
    """
    Get session details including IP addresses.

    Args:
        days: Number of days to include
        limit: Max number of sessions to return
    """
    return {
        "sessions": analytics.get_sessions(limit=limit, days=days),
        "unique_ips": analytics.get_unique_ips(days=days)
    }


class TrackRequest(BaseModel):
    session_id: str
    event: str = "page_view"
    page: str = "/"
    user_agent: Optional[str] = None


@app.post("/track", response_model=dict)
async def track_event(request: TrackRequest, req: Request):
    """
    Track a page view or event.
    """
    analytics.log_page_view(
        session_id=request.session_id,
        page=request.page,
        ip_address=get_real_ip(req),
        user_agent=request.user_agent
    )
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    # Get port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    # Disable reload in production (when running on Render)
    is_production = os.getenv("RENDER", False)

    print("="*80)
    print("IDAHO ALF REGNAVIGATOR API")
    print("="*80)
    print(f"Starting server on http://localhost:{port}")
    print(f"API docs: http://localhost:{port}/docs")
    print(f"Environment: {'Production' if is_production else 'Development'}")
    print("="*80 + "\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=not is_production
    )
