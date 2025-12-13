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
    session_id: Optional[str] = None  # For analytics tracking


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
    Answer a question about Idaho ALF regulations.

    Args:
        request: QueryRequest with question and optional conversation history

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

        # Get answer from RAG engine
        result = rag_engine.answer_question(
            question=request.question,
            conversation_history=conversation_history,
            top_k=request.top_k,
            temperature=request.temperature,
            verbose=False
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
            ip_address=req.client.host if req.client else None
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


@app.get("/library", response_model=dict)
async def get_library():
    """
    Get hierarchically organized regulation library.
    Returns a tree structure for navigation.
    """
    import re
    from collections import defaultdict

    if rag_engine is None:
        raise HTTPException(status_code=503, detail="RAG engine not initialized")

    # Build hierarchical structure
    library = []

    # Helper to get document category
    def categorize_chunk(chunk):
        source = chunk.get('source_file', '')
        citation = chunk.get('citation', '')

        if 'ADA' in source:
            return ('ADA Accessibility Guidelines', 'ada')
        elif 'Food Code' in source and 'IDAPA' not in source:
            return ('FDA Food Code', 'fda')
        elif 'IDAPA 16.03.22' in citation or 'IDAPA 16.txt' in source:
            return ('IDAPA 16.03.22 - Residential Care Facilities', 'idapa-16-03-22')
        elif 'IDAPA 16.02' in citation:
            return ('IDAPA 16.02 - Public Health', 'idapa-16-02')
        elif 'IDAPA 16.05' in citation:
            return ('IDAPA 16.05 - Administration', 'idapa-16-05')
        elif 'IDAPA 24.34' in citation:
            return ('IDAPA 24.34.01 - Board of Nursing', 'idapa-24-34')
        elif 'IDAPA 24.39' in citation:
            return ('IDAPA 24.39.30 - Building Safety', 'idapa-24-39')
        elif 'IDAPA 24' in citation:
            return ('IDAPA 24 - Occupational Licenses', 'idapa-24')
        elif 'Title 39' in citation or 'TITLE 39' in source:
            return ('Idaho Code Title 39 - ALF Act', 'title-39')
        elif 'Title 74' in citation:
            return ('Idaho Code Title 74 - Public Records', 'title-74')
        elif 'reference' in source.lower():
            return ('Reference Documents', 'references')
        else:
            return ('Other Regulations', 'other')

    # Group chunks by document type
    doc_groups = defaultdict(list)
    for chunk in rag_engine.chunks:
        doc_name, doc_id = categorize_chunk(chunk)
        doc_groups[(doc_name, doc_id)].append(chunk)

    # Process each document type
    for (doc_name, doc_id), chunks in sorted(doc_groups.items()):
        doc_node = {
            'id': doc_id,
            'name': doc_name,
            'type': 'document',
            'count': len(chunks),
            'children': []
        }

        # Sub-group based on document type
        if doc_id == 'ada':
            # Group ADA by main section number
            sections = defaultdict(list)
            section_names = {
                '1': 'Purpose',
                '2': 'General',
                '3': 'Definitions',
                '4': 'Accessible Elements & Spaces',
                '5': 'Restaurants & Cafeterias',
                '6': 'Medical Care Facilities',
                '7': 'Business & Mercantile',
                '8': 'Libraries',
                '9': 'Accessible Transient Lodging',
                '10': 'Transportation Facilities'
            }
            for c in chunks:
                match = re.search(r'\.(\d+)\.', c['citation'])
                if match:
                    sec_num = match.group(1)
                    sections[sec_num].append(c)

            for sec_num in sorted(sections.keys(), key=int):
                sec_name = section_names.get(sec_num, f'Section {sec_num}')
                sec_chunks = sections[sec_num]

                # Further group by subsection (4.1, 4.2, etc.)
                subsections = defaultdict(list)
                for c in sec_chunks:
                    match = re.search(r'\.(\d+\.\d+)', c['citation'])
                    if match:
                        subsections[match.group(1)].append(c)
                    else:
                        subsections['_main'].append(c)

                sec_node = {
                    'id': f'{doc_id}-sec-{sec_num}',
                    'name': f'Section {sec_num}: {sec_name}',
                    'type': 'section',
                    'count': len(sec_chunks),
                    'children': []
                }

                for subsec_num in sorted(subsections.keys()):
                    if subsec_num == '_main':
                        continue
                    subsec_chunks = subsections[subsec_num]
                    # Get first chunk's title for subsection name
                    subsec_title = subsec_chunks[0].get('section_title', '')[:50]
                    sec_node['children'].append({
                        'id': f'{doc_id}-{subsec_num}',
                        'name': f'{subsec_num} - {subsec_title}',
                        'type': 'subsection',
                        'count': len(subsec_chunks),
                        'chunks': [{'chunk_id': c['chunk_id'], 'citation': c['citation'],
                                   'title': c['section_title'][:60]} for c in subsec_chunks]
                    })

                doc_node['children'].append(sec_node)

        elif doc_id == 'fda':
            # Group FDA by chapter
            chapters = defaultdict(list)
            chapter_names = {
                '1': 'Purpose & Definitions',
                '2': 'Management & Personnel',
                '3': 'Food',
                '4': 'Equipment, Utensils & Linens',
                '5': 'Water, Plumbing & Waste',
                '6': 'Physical Facilities',
                '7': 'Poisonous Materials',
                '8': 'Compliance & Enforcement'
            }
            for c in chunks:
                match = re.search(r'\.(\d)-', c['citation'])
                if match:
                    chapters[match.group(1)].append(c)

            for ch_num in sorted(chapters.keys(), key=int):
                ch_name = chapter_names.get(ch_num, f'Chapter {ch_num}')
                ch_chunks = chapters[ch_num]

                # Group by part (3-1, 3-2, etc.)
                parts = defaultdict(list)
                for c in ch_chunks:
                    match = re.search(r'\.(\d-\d)', c['citation'])
                    if match:
                        parts[match.group(1)].append(c)

                ch_node = {
                    'id': f'{doc_id}-ch-{ch_num}',
                    'name': f'Chapter {ch_num}: {ch_name}',
                    'type': 'chapter',
                    'count': len(ch_chunks),
                    'children': []
                }

                for part_num in sorted(parts.keys()):
                    part_chunks = parts[part_num]
                    ch_node['children'].append({
                        'id': f'{doc_id}-{part_num}',
                        'name': f'Part {part_num}',
                        'type': 'part',
                        'count': len(part_chunks),
                        'chunks': [{'chunk_id': c['chunk_id'], 'citation': c['citation'],
                                   'title': c['section_title'][:60]} for c in part_chunks[:20]]  # Limit for performance
                    })

                doc_node['children'].append(ch_node)

        elif doc_id.startswith('idapa'):
            # Group IDAPA by section number range
            section_ranges = [
                ('000-099', 'Administrative & Definitions'),
                ('100-199', 'Licensing'),
                ('200-299', 'Admission & Discharge'),
                ('300-399', 'Records & Services'),
                ('400-499', 'Staffing'),
                ('500-599', 'Resident Care'),
                ('600-699', 'Medications'),
                ('700-799', 'Dietary'),
                ('800-899', 'Physical Plant'),
                ('900-999', 'Enforcement')
            ]

            for range_str, range_name in section_ranges:
                start, end = map(int, range_str.split('-'))
                range_chunks = []
                for c in chunks:
                    match = re.search(r'\.(\d{1,3})(?:\s|\(|$)', c['citation'])
                    if match:
                        num = int(match.group(1))
                        if start <= num <= end:
                            range_chunks.append(c)

                if range_chunks:
                    doc_node['children'].append({
                        'id': f'{doc_id}-{range_str}',
                        'name': f'Sections {range_str}: {range_name}',
                        'type': 'section-range',
                        'count': len(range_chunks),
                        'chunks': [{'chunk_id': c['chunk_id'], 'citation': c['citation'],
                                   'title': c['section_title'][:60]} for c in range_chunks]
                    })

        elif doc_id in ('title-39', 'title-74'):
            # Group Idaho Code by section
            for c in chunks:
                doc_node['children'].append({
                    'id': c['chunk_id'],
                    'name': c['citation'].split('.')[-1] + ' - ' + c['section_title'][:50],
                    'type': 'statute',
                    'count': 1,
                    'chunks': [{'chunk_id': c['chunk_id'], 'citation': c['citation'],
                               'title': c['section_title'][:60]}]
                })

        else:
            # Default: flat list
            for c in chunks:
                doc_node['children'].append({
                    'id': c['chunk_id'],
                    'name': c['section_title'][:60] or c['citation'],
                    'type': 'chunk',
                    'count': 1,
                    'chunks': [{'chunk_id': c['chunk_id'], 'citation': c['citation'],
                               'title': c['section_title'][:60]}]
                })

        library.append(doc_node)

    # Sort library by document name
    library.sort(key=lambda x: x['name'])

    return {
        'total_documents': len(library),
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
        ip_address=req.client.host if req.client else None,
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
