# Senior Chatbots - Project Context

## Overview

This project contains two AI-powered chatbots designed for the senior care industry:

1. **Medicaid Chatbot** - Answers questions about SNF (Skilled Nursing Facility) Medicaid reimbursement policies for all 50 US states
2. **Idaho ALF Chatbot** - Answers questions about Idaho Assisted Living Facility regulations (IDAPA 16.03.22)

Both chatbots use RAG (Retrieval-Augmented Generation) to provide accurate, citation-backed answers from authoritative source documents.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│                    React + Vite (port 4005)                     │
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │  MedicaidChatbot    │    │  IdahoALFChatbot    │            │
│  │  - State selector   │    │  - Chat interface   │            │
│  │  - Revenue dashboard│    │  - Regulation library│            │
│  │  - Deep Analysis    │    │  - Inline citations │            │
│  └─────────────────────┘    └─────────────────────┘            │
└─────────────────────────────────────────────────────────────────┘
                │                           │
                ▼                           ▼
┌───────────────────────────┐  ┌───────────────────────────┐
│   MEDICAID BACKEND        │  │   ALF BACKEND             │
│   Node.js/Express (3001)  │  │   Python/FastAPI (8000)   │
│                           │  │                           │
│  ┌─────────────────────┐  │  │  ┌─────────────────────┐  │
│  │ vectorSearch.js     │  │  │  │ rag_engine.py       │  │
│  │ - Xenova/MiniLM     │  │  │  │ - OpenAI embeddings │  │
│  │ - Cosine similarity │  │  │  │ - Cosine similarity │  │
│  └─────────────────────┘  │  │  └─────────────────────┘  │
│                           │  │                           │
│  ┌─────────────────────┐  │  │  ┌─────────────────────┐  │
│  │ aiService.js        │  │  │  │ claude_client.py    │  │
│  │ - Claude (primary)  │  │  │  │ - Claude API        │  │
│  │ - OpenAI (fallback) │  │  │  │                     │  │
│  └─────────────────────┘  │  │  └─────────────────────┘  │
└───────────────────────────┘  └───────────────────────────┘
                │                           │
                ▼                           ▼
┌───────────────────────────┐  ┌───────────────────────────┐
│   MEDICAID DATA           │  │   ALF DATA                │
│                           │  │                           │
│ • medicaid-policies-      │  │ • chunks_with_embeddings  │
│   structured.json         │  │   .json (75MB)            │
│   (All 50 states)         │  │                           │
│                           │  │ • Raw IDAPA regulations   │
│ • embeddings/idaho.json   │  │ • ADA guidelines          │
│   (RAG for Idaho only)    │  │ • Food code               │
└───────────────────────────┘  └───────────────────────────┘
```

---

## Tech Stack

### Frontend
| Technology | Purpose |
|------------|---------|
| React 19 | UI framework |
| Vite 7 | Build tool & dev server |
| React Router | Navigation |
| Lucide React | Icons |
| React Markdown | Rendering AI responses |

### Medicaid Backend (Node.js)
| Technology | Purpose |
|------------|---------|
| Express 5 | HTTP server |
| @anthropic-ai/sdk | Claude API client |
| @xenova/transformers | Local embedding model (MiniLM-L6) |
| OpenAI SDK | Fallback AI & embeddings |

### ALF Backend (Python)
| Technology | Purpose |
|------------|---------|
| FastAPI | HTTP server |
| Anthropic SDK | Claude API client |
| OpenAI SDK | Embeddings (text-embedding-3-large) |
| NumPy | Vector operations |
| Pydantic | Request/response validation |

---

## RAG Implementation

### How RAG Works

1. **Document Processing** (done once)
   - Source documents are split into chunks
   - Each chunk is converted to a vector embedding
   - Embeddings are stored in JSON files

2. **Query Processing** (each question)
   - User question is converted to a vector embedding
   - Cosine similarity finds most relevant chunks
   - Top-K chunks are retrieved as context
   - Context + question sent to Claude for answer generation

### Medicaid Chatbot RAG

- **Embedding Model**: Xenova/all-MiniLM-L6-v2 (runs locally in Node.js)
- **Coverage**: Idaho only (other states use policy JSON without RAG)
- **Trigger**: "Deep Analysis" toggle in UI
- **Data Path**: `backend/medicaid/data/embeddings/idaho.json`

### ALF Chatbot RAG

- **Embedding Model**: OpenAI text-embedding-3-large (API call)
- **Coverage**: Full Idaho ALF regulations
- **Trigger**: Always active for every query
- **Data Path**: `backend/alf/data/processed/chunks_with_embeddings.json`

---

## Data Sources

### Medicaid Chatbot

| Source | Description |
|--------|-------------|
| `medicaid-policies-structured.json` | All 50 states' SNF Medicaid policies |
| `medicaid-source-urls.json` | URLs to source documents |
| `embeddings/idaho.json` | Pre-computed embeddings for Idaho |

**Policy Categories:**
- Payment methodology (per diem, case-mix, etc.)
- Quality incentive programs
- Supplemental payments
- Rate rebasing schedules
- Bed-hold policies
- Acuity/case-mix systems

### ALF Chatbot

| Source | Description |
|--------|-------------|
| IDAPA 16.03.22 | Idaho Residential Care/ALF regulations |
| IDAPA 16.05.06 | Criminal background check requirements |
| IDAPA 16.02.19 | Food code requirements |
| Title 39 Chapter 33 | Idaho Residential Care Act |
| ADA Guidelines | Accessibility requirements |
| US Public Health Food Code | Food safety standards |

**Regulation Categories:**
- Administrative
- Licensing
- Staffing
- Physical Plant
- Fire Safety
- Medications
- Resident Care
- Food Service

---

## API Endpoints

### Medicaid Backend (port 3001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/medicaid/states` | GET | List all available states |
| `/api/medicaid/policies/:state` | GET | Get policies for a state |
| `/api/medicaid/chat` | POST | Ask a question |
| `/api/medicaid/revenue-levers/:state` | GET | Get revenue opportunities |
| `/health` | GET | Health check |

**Chat Request:**
```json
{
  "state": "Idaho",
  "question": "What is the per diem rate?",
  "conversationHistory": [],
  "deepAnalysis": true
}
```

### ALF Backend (port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/query` | POST | Ask a question |
| `/chunks` | GET | List all regulation chunks |
| `/categories` | GET | List regulation categories |
| `/health` | GET | Health check |

**Query Request:**
```json
{
  "question": "What are the staffing requirements?",
  "conversation_history": [],
  "top_k": 12,
  "temperature": 0.5
}
```

---

## Environment Variables

```bash
# API Keys
ANTHROPIC_API_KEY=sk-ant-...    # Required for Claude
OPENAI_API_KEY=sk-proj-...      # Required for embeddings & fallback

# Server Ports
MEDICAID_PORT=3001
ALF_PORT=8000

# Frontend (optional, for production)
VITE_MEDICAID_API_URL=http://localhost:3001
VITE_ALF_API_URL=http://localhost:8000
```

---

## Running the Project

### Development

```bash
# Terminal 1 - Frontend
cd frontend && npm run dev

# Terminal 2 - Medicaid Backend
cd backend/medicaid && npm start

# Terminal 3 - ALF Backend
cd backend/alf && python main.py
```

### Or run all together:
```bash
npm run dev  # Uses concurrently to run all services
```

### URLs
- Frontend: http://localhost:4005
- Medicaid API: http://localhost:3001
- ALF API: http://localhost:8000
- ALF API Docs: http://localhost:8000/docs

---

## Key Files

### Frontend
```
frontend/
├── src/
│   ├── App.jsx                    # Main router
│   ├── components/
│   │   ├── MedicaidChatbot.jsx    # Medicaid UI (623 lines)
│   │   ├── MedicaidChatbot.css
│   │   ├── IdahoALFChatbot.jsx    # ALF UI (708 lines)
│   │   └── IdahoALFChatbot.css
│   └── services/
│       └── apiService.js          # API client functions
```

### Medicaid Backend
```
backend/medicaid/
├── server.js                      # Express server
├── routes/
│   └── medicaid.js                # API routes (606 lines)
├── services/
│   ├── aiService.js               # Claude/OpenAI client
│   ├── vectorSearch.js            # RAG search
│   └── documentFetcher.js         # Document retrieval
└── data/
    ├── medicaid-policies-structured.json
    └── embeddings/idaho.json
```

### ALF Backend
```
backend/alf/
├── main.py                        # FastAPI server
├── rag_engine.py                  # RAG implementation
├── embeddings.py                  # Embedding generation
├── claude_client.py               # Claude API client
├── ai_service.py                  # Unified AI service
└── data/
    ├── raw/                       # Source regulation files
    └── processed/
        └── chunks_with_embeddings.json
```

---

## Future Improvements

### Medicaid Chatbot
- [ ] Generate embeddings for all 50 states (currently only Idaho)
- [ ] Add more policy document sources
- [ ] Implement conversation memory/context

### ALF Chatbot
- [ ] Expand to other states beyond Idaho
- [ ] Add more regulation categories
- [ ] Improve citation formatting

### General
- [ ] Add user authentication
- [ ] Implement usage analytics
- [ ] Add rate limiting
- [ ] Deploy to production (Render, Vercel, etc.)

---

## Troubleshooting

### "No embeddings found for [state]"
- Only Idaho has RAG embeddings for Medicaid chatbot
- Other states will still work using the JSON policy data

### "RAG engine not initialized"
- Check that `chunks_with_embeddings.json` exists in ALF data folder
- Verify the file path in `main.py`

### API key errors
- Ensure `.env` file exists with valid keys
- Check that keys haven't been revoked

### Port already in use
- Kill existing processes: `pkill -f vite` or `pkill -f node`
- Check what's using the port: `lsof -i :4005`
