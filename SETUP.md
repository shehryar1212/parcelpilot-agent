# ParcelPilot Agent – Local Setup

## Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 16 (local or Docker)
- OpenAI API key

## 1. Environment Setup

Copy `.env.example` to `.env` and fill in your OpenAI API key:

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## 2. PostgreSQL Setup (Docker)

**Quick start with Docker:**

```bash
docker run --name parcelpilot-db \
  -e POSTGRES_DB=parcelpilot \
  -e POSTGRES_PASSWORD=devpass \
  -p 5432:5432 \
  postgres:16
```

Or if you have PostgreSQL installed locally, create the database:

```bash
createdb parcelpilot
```

Update `DATABASE_URL` in `.env` to match your setup:
- Local: `postgresql://localhost:5432/parcelpilot`
- Docker: `postgresql://postgres:devpass@localhost:5432/parcelpilot`
- Neon (production): `postgresql://user:password@ep-xxx.neon.tech/parcelpilot`

## 3. Backend Setup

```bash
cd backend
python -m venv venv

# Activate venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### Initialize database schema:

```bash
python -c "from db.config import init_db; init_db()"
```

This runs `backend/db/schema.sql` and sets up tables with idempotent CREATE TABLE IF NOT EXISTS.

### Run the backend:

```bash
python main.py
# or
uvicorn main:app --reload
```

Backend runs on `http://localhost:8000`

## 4. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:3000`

## 5. Next Steps

Once both are running:

1. **Load data:** Run `backend/db/load_data.py` to populate accounts, orders, tickets from xlsx
2. **Chunk documents:** Run `backend/db/chunk_documents.py` to create doc chunks
3. **Embed chunks:** Run `backend/db/embed_chunks.py` to embed and load into Postgres
4. **Test tools:** Test each tool endpoint independently
5. **Build agent:** Wire up the agent loop with OpenAI
6. **Build UI:** Create the chat interface in Next.js

## Testing

```bash
# Backend tests (when created)
pytest backend/tests/

# Frontend tests (when created)
npm test
```

## Troubleshooting

**"Connection refused" when connecting to Postgres:**
- Ensure Docker container is running: `docker ps`
- Or ensure PostgreSQL service is running locally
- Check DATABASE_URL is correct

**Module not found errors:**
- Ensure you activated the Python venv
- Reinstall dependencies: `pip install -r requirements.txt`

**CORS errors in frontend:**
- Ensure backend is running on http://localhost:8000
- Check NEXT_PUBLIC_API_URL in `.env` (or .env.local)

**OpenAI API errors:**
- Verify OPENAI_API_KEY is set in `.env`
- Check your API key is valid and has quota
