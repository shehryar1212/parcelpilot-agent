# ParcelPilot AI Agent

A production-ready AI chatbot for B2B logistics (ParcelPilot) supporting customer-facing and internal support workflows. Built with FastAPI, Next.js, Postgres, and OpenAI.

**Live Demo:**
- **Frontend:** https://frontend-lilac-pi-66.vercel.app
- **Backend:** https://parcelpilot-agent-ler7.onrender.com
- **Database:** Neon PostgreSQL (pgvector)

## Architecture

```
frontend (Next.js)        backend (FastAPI)              database (Postgres)
   ↓                         ↓                              ↓
  chat UI        →  agent loop (gpt-4o)   →     structured data
  (React)            ↓                         doc chunks (pgvector)
               3 tools:
               - search_documents
               - query_structured_data
               - prepare_action/execute_action
```

**Key features:**
- Source precedence encoded in system prompt: contract > SOP > policy > historical notes
- Two-phase actions (prepare → confirm → execute) for risk management
- Session-based auth (customer vs staff) enforced in dependency layer
- Metadata-filtered retrieval to avoid embedding ranking errors
- Transparent tool tracing in chat UI

## Project Structure

```
parcelpilot/
├── backend/
│   ├── db/
│   │   ├── config.py           # Database connection & init
│   │   ├── schema.sql          # Idempotent schema
│   │   ├── chunk_documents.py  # Chunk PDFs by section
│   │   ├── embed_chunks.py     # Embed + load chunks
│   │   └── load_data.py        # Load structured data from xlsx
│   ├── routes/
│   │   └── chat.py             # Chat endpoint (to build)
│   ├── auth.py                 # Session mocking
│   ├── models.py               # Pydantic models
│   ├── main.py                 # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── pages/
│   │   ├── _app.tsx
│   │   └── index.tsx           # Chat UI
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.js
├── .env.example
├── SETUP.md                    # Local dev setup
└── README.md
```

## Quick Start

### 1. Prerequisites

```bash
# Python 3.10+
python --version

# Node.js 18+
node --version

# PostgreSQL (local or Docker)
# Docker: docker run -e POSTGRES_DB=parcelpilot -e POSTGRES_PASSWORD=devpass -p 5432:5432 postgres:16
```

### 2. Environment

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key
export OPENAI_API_KEY=sk-...
```

### 3. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Initialize database schema
python -c "from db.config import init_db; init_db()"

# Start backend
python main.py
# → Backend runs on http://localhost:8000
```

### 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
# → Frontend runs on http://localhost:3000
```

## Data Pipeline (Phase 2)

Once both backend and frontend are running, load your data:

### Step 1: Chunk Documents

```bash
cd backend
python db/chunk_documents.py
# → Outputs chunks.json for review
```

Review `backend/db/chunks.json` to verify sections are split correctly. The chunks should be semantically complete units (one section per chunk).

### Step 2: Embed Chunks

```bash
python db/embed_chunks.py
# → Embeds chunks with text-embedding-3-small (1536 dims)
# → Loads into doc_chunks table
```

### Step 3: Load Structured Data

```bash
python db/load_data.py
# → Populates accounts, orders, tickets from xlsx
```

Verify data loaded:

```bash
# In psql or any Postgres client:
SELECT COUNT(*) FROM accounts;  -- Should be 4
SELECT COUNT(*) FROM orders;    -- Should be 7
SELECT COUNT(*) FROM tickets;   -- Should be 8
SELECT COUNT(*) FROM doc_chunks; -- Should be ~20-25
```

## Tool Implementation (Phase 3)

Three core tools to build:

### 1. `search_documents`

```python
def search_documents(query: str, account_id: Optional[str] = None) -> List[DocChunk]:
    """
    Search documents with metadata filtering for source precedence.
    - Pre-filter by doc_type and status
    - Rank by embedding similarity
    - Exclude deprecated docs from default search
    """
```

**Metadata filtering rules:**
1. Always include customer-specific contracts (customer_account_id = account_id)
2. Always include current policies/SOPs (status = 'current')
3. Never include deprecated docs unless explicitly requested
4. Rank contracts above policies above product docs

### 2. `query_structured_data`

```python
def query_structured_data(
    query_type: str,  # 'orders', 'tickets', 'account_details'
    account_id: str,
    filters: dict = {}
) -> List[Any]:
    """Query operational data with safety checks."""
```

### 3. `prepare_action` / `execute_action`

```python
def prepare_action(
    action_type: str,  # 'escalation', 'ticket_update', 'follow_up_task'
    account_id: str,
    payload: dict,
    preview_text: str,
    session: Session,
) -> AgentAction:
    """Create pending_confirmation action."""

def execute_action(
    action_id: UUID,
    session: Session,
) -> AgentAction:
    """Flip action from pending → executed. Requires confirmation."""
```

## Agent Loop (Phase 4)

The agent uses Claude's tool-use API via OpenAI's API:

```python
# backend/agent.py (to build)

def run_agent(
    user_message: str,
    session: Session,
    context: dict = {},
) -> AgentResponse:
    """
    Agent loop with OpenAI gpt-4o.
    
    1. Encode source precedence in system prompt
    2. Call search_documents with metadata filters
    3. Call query_structured_data for operational context
    4. Prepare actions (two-phase, shown to user for confirmation)
    5. Return reply + tool calls for transparency
    """
```

**System prompt key rules:**
- Contracts are authoritative; policies are default fallbacks
- Historical ticket resolutions are context-only, never authoritative
- Escalate if uncertain; don't guess
- Always check for known issues before troubleshooting
- SLA breaches are P1; confirm before taking action
- Credits over ₹1,000 require manager approval

## Testing

Test each tool independently before wiring to agent:

```bash
# In Python REPL or tests/
from db.config import engine
from tools import search_documents, query_structured_data

# Test search
chunks = search_documents("cancellation fee", account_id="ACCT-001")
assert len(chunks) > 0

# Test query
orders = query_structured_data("orders", account_id="ACCT-001")
assert any(o.order_id == "ORD-1001" for o in orders)
```

## Deployment (Production)

### Current Setup
- **Frontend:** Vercel (https://frontend-lilac-pi-66.vercel.app)
- **Backend:** Render (https://parcelpilot-agent-ler7.onrender.com)
- **Database:** Neon PostgreSQL

### Environment Variables (Required)
```
OPENAI_API_KEY=sk-...
DATABASE_URL=postgresql+psycopg://...@neon.tech/...
NEXT_PUBLIC_API_URL=https://parcelpilot-agent-ler7.onrender.com
FRONTEND_URL=https://frontend-lilac-pi-66.vercel.app
```

### Deploy Steps
1. Push to GitHub
2. Vercel auto-deploys frontend on push
3. Render auto-deploys backend on push
4. Load data into Neon: `python db/embed_chunks.py && python db/load_data.py`

## Known Dataset Traps

The test data has specific edge cases the agent must handle correctly:

1. **Northstar contract waives cancellation fee** (ORD-1001) – contract overrides SOP
2. **TKT-450 is wrong** – agent shouldn't repeat historical mistakes
3. **LumenWorks contract replaces SOP credit terms** (ORD-2002) – use contract number, not SOP
4. **TKT-451 claims wrong Growth plan limit** – product doc says 5k, not 3k
5. **SwiftShip webhook delay** (TKT-504, KI-211) – up to 20 min late, not a bug
6. **Credential exposure is P1** (TKT-505, SLA breach) – classify correctly
7. **TKT-501 SLA breach** (Northstar, P1, 15 min target) – already breached
8. **TKT-503 needs escalation** – not in supplied docs, don't guess

## Status: Production-Ready ✅

### Completed
- [x] Load data via chunk_documents.py, embed_chunks.py, load_data.py
- [x] Implement `search_documents` tool with metadata filtering
- [x] Implement `query_structured_data` tool for orders/tickets/accounts
- [x] Implement `prepare_action` / `execute_action` tools (two-phase)
- [x] Build agent loop with OpenAI gpt-4o
- [x] Wire chat endpoint to agent
- [x] Chat UI with tool transparency and session switching
- [x] Deploy frontend to Vercel
- [x] Deploy backend to Render
- [x] Deploy database to Neon PostgreSQL
- [x] Test all 8 dataset edge cases ✓

### Future Enhancements
- [ ] Record ~5 min demo video
- [ ] Write architecture note
- [ ] Write product note (roadmap for v2 features)
- [ ] Add action confirmation UI cards
- [ ] Add conversation history persistence
- [ ] Add analytics/logging dashboard

## Support

- Setup issues? See [SETUP.md](./SETUP.md)
- Stuck on a piece? Ask me directly
- Need to adjust? Code is yours—refactor as needed

---

Built with 🚀 for ParcelPilot AI assessment.
