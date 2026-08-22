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
│   │   └── chat.py             # Chat endpoint
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

## Data Pipeline

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

## Core Tools

Three core tools implemented:

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

## Agent Loop

The agent uses OpenAI's API with tool use:

```python
# backend/agent.py

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

All 8 dataset edge cases validated. Test in browser:

1. **Customer session:** Select customer from dropdown, ask questions about own orders/tickets
   - Should only see own data, not other customers' orders
   
2. **Staff session:** Select staff role, can access all customer data
   - Should find contract overrides, known issues, SLA breaches
   
3. **Edge cases verified:**
   - Contracts override SOPs ✓
   - Historical mistakes flagged ✓
   - Known issues identified ✓
   - Credential exposure = P1 ✓
   - SLA breach detection ✓
   - Escalation when uncertain ✓

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
- [x] Build agent loop with OpenAI gpt-4o-mini
- [x] Wire chat endpoint to agent
- [x] Chat UI with tool transparency and session switching
- [x] Deploy frontend to Vercel
- [x] Deploy backend to Render
- [x] Deploy database to Neon PostgreSQL
- [x] Test all 8 dataset edge cases ✓
- [x] Security fixes: Fix 1-4 (cross-tenant isolation, SQL injection prevention, account resolution, time grounding)
- [x] Customer-initiated cancellation requests (narrowly scoped, server-enforced ownership)

### Future Enhancements
- [ ] Record ~5 min demo video
- [ ] Write architecture note
- [ ] Write product note (roadmap for v2 features)
- [ ] Add action confirmation UI cards
- [ ] Add conversation history persistence
- [ ] Add analytics/logging dashboard

## Design Decisions

### Customer-Facing Bot: Read + Cancellation Request Only
Customers can query their own orders, tickets, contracts, and policies. They can also request cancellation of their own orders via `prepare_action(action_type="cancellation_request", order_id=...)`. This is narrowly scoped:
- Customers can only cancel their own orders (server-enforced account_id check)
- Cancellation fee determination uses source precedence (contract > SOP)
- Cannot initiate credits, escalations, or other state changes
- ParcelPilot CSMs handle broader operational decisions
- Reduces surface area while enabling a key self-service action

### Staff Bot: Full Action Capability
Internal support staff can search all customer data, prepare actions (with preview + confirmation), and execute them. This allows efficient support workflows while maintaining two-phase confirmation for high-stakes changes.

### Time-Grounded Agent
The agent uses `dataset_meta.snapshot_at` (2026-08-16 11:00 Asia/Kolkata) as the reference time for all SLA/lateness calculations, not the server's wall-clock date. This makes reasoning reproducible and dataset-specific.

## Support

- Setup issues? See [SETUP.md](./SETUP.md)
- Stuck on a piece? Ask me directly
- Need to adjust? Code is yours—refactor as needed

---

Built with 🚀 for ParcelPilot AI assessment.
