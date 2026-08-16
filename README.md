<<<<<<< HEAD
# Antigen — Local Chat Assistant

Scaffold for a local chat assistant using FastAPI (backend), React + Vite (frontend), and Postgres (optional via Docker Compose).

Quick start (local dev):

1. Backend

Install Python dependencies and run the API:

```bash
python -m pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2. Frontend

```bash
cd frontend
npm install
npm run dev
```

3. Postgres (optional)

```bash
docker compose up -d
```

Set `OPENAI_API_KEY` in your environment before using the chat endpoint.

PGVector / Embeddings setup

If you plan to use semantic search (embeddings + `pgvector`), ensure the Postgres `vector` extension is available. When using the provided Docker Compose, you can enable it by connecting to the DB container and running:

```bash
docker compose exec db bash
psql -U antigen -d antigen -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Install backend dependencies (including `pgvector` and `openai`) and run the backend:

```bash
python -m pip install -r backend/requirements.txt
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Quick semantic search test

1. Create a memory (replace OPENAI_API_KEY in your env):

```bash
curl -X POST http://localhost:8000/memories \
	-H 'Content-Type: application/json' \
	-d '{"type":"note","content":"Remember to review the budget report on Friday.","tags":"work,finance"}'
```

2. Run a semantic search:

```bash
curl -X POST http://localhost:8000/memories/semantic_search \
	-H 'Content-Type: application/json' \
	-d '{"query":"budget report review next week"}'
```

The backend will compute an embedding for the query and return relevant memories ordered by similarity.

=======
# Antigen-Chat-Assistant
>>>>>>> 17f19998f14081b5b147fb5c9501da97b161d3d6
