# Full-Stack RAG Starter

A clean full-stack Retrieval-Augmented Generation starter with:

- Frontend: React, Vite, TypeScript, Tailwind CSS
- Backend: FastAPI, Pydantic settings, layered clean architecture
- Local retrieval: sentence-transformers embeddings stored in ChromaDB
- Answer generation: Gemini API with grounded prompts and source citations
- Authentication: bcrypt password hashing, JWT access/refresh tokens, role-aware user profiles
- Development workflow: separate frontend/backend apps, CORS, environment files

## Project Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/              # HTTP routes and schemas
│   │   ├── application/      # Use-case services
│   │   ├── core/             # Settings and app configuration
│   │   ├── domain/           # Entities and repository interfaces
│   │   ├── infrastructure/   # File storage, extractors, embeddings, vector store
│   │   └── main.py           # FastAPI app factory
│   ├── .env.example
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── api/              # Typed backend client
    │   ├── components/       # Reusable UI components
    │   ├── types/            # Shared TypeScript types
    │   └── App.tsx
    ├── .env.example
    └── package.json
```

## Prerequisites

- Python 3.11+
- Node.js 20+

## Run Locally

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

On macOS/Linux, use `source .venv/bin/activate` and `cp .env.example .env`.

Backend health check:

```bash
curl http://localhost:8000/health
```

### 2. Frontend

```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Open the Vite URL, usually [http://localhost:5173](http://localhost:5173).

## How It Works

1. Register or log in to create a private workspace.
2. Upload `.pdf`, `.docx`, or `.txt` files from the frontend.
2. The backend stores the original file locally in `backend/storage/uploads`.
3. Text is extracted with format-specific parsers.
4. Extracted text is split into configurable semantic chunks.
5. Chunk embeddings are generated with `sentence-transformers/all-MiniLM-L6-v2`.
6. Chunks, embeddings, and metadata are persisted in ChromaDB.
7. Ask a question.
8. The backend retrieves only the authenticated user's chunks and asks the configured LLM to return a validated structured JSON answer with citations.

This starter uses local embeddings, ChromaDB, and SQLite for users, tokens, documents, chats, and messages. The first upload or query may download the embedding model from Hugging Face. Swap implementations in `backend/app/infrastructure/` when adding a hosted vector database, Postgres, or another LLM provider.

## Environment Variables

Backend (`backend/.env`):

```env
APP_NAME=RAG Starter API
ENVIRONMENT=development
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
MAX_UPLOAD_BYTES=2097152
CHUNK_SIZE=900
CHUNK_OVERLAP=120
UPLOAD_DIR=storage/uploads
METADATA_PATH=storage/documents.json
CHROMA_PATH=storage/chroma
CHROMA_COLLECTION=rag_documents
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_CACHE_FOLDER=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.2
GEMINI_MAX_OUTPUT_TOKENS=1024
DATABASE_PATH=storage/rag.sqlite3
JWT_SECRET_KEY=replace-with-a-long-random-secret
JWT_ISSUER=rag-starter
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=14
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30
APP_BASE_URL=http://127.0.0.1:5173
SENDGRID_API_KEY=
SENDGRID_FROM_EMAIL=RAG Starter <noreply@your-verified-domain.com>
```

Frontend (`frontend/.env`):

```env
VITE_API_BASE_URL=http://localhost:8000
```

Set `GEMINI_API_KEY` before using `/api/chat`. `/api/search` works without Gemini because it only performs embedding retrieval from ChromaDB.

## Password Reset with SendGrid

The forgot-password flow emails a one-time reset link through the [SendGrid](https://sendgrid.com) Mail Send API. Reset tokens are hashed before storage, expire after `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` (30 minutes by default), and can only be used once. The forgot-password endpoint always returns the same generic response whether or not the email exists, so it cannot be used to enumerate accounts.

To enable delivery:

1. Create a SendGrid account and generate an API key with Mail Send permission.
2. Verify a sender identity (or domain) in SendGrid and set `SENDGRID_FROM_EMAIL` to that address in `Name <email>` format, for example `RAG Starter <noreply@your-verified-domain.com>`. SendGrid rejects mail from unverified senders.
3. Set these values in `backend/.env`:

```env
PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30
APP_BASE_URL=http://127.0.0.1:5173
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=RAG Starter <noreply@your-verified-domain.com>
```

4. Restart the backend, then use "Forgot password?" on the login screen.

`APP_BASE_URL` is the frontend origin used to build the reset link (`<APP_BASE_URL>/reset-password?token=...`); update it if the frontend is served from a different host in production. Never commit real API keys — keep them in `backend/.env` only.

Until `SENDGRID_API_KEY` is set, the forgot-password endpoint returns `503` with a message explaining that reset email is not configured; everything else in the app works normally, and the reset-password endpoint itself still functions for tokens that were already issued.

## API Endpoints

Register and capture an access token:

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Demo User\",\"email\":\"demo@example.com\",\"password\":\"StrongPass123!\"}"
```

Protected endpoints require `Authorization: Bearer <access_token>`.

Upload and index a document:

```bash
curl -F "file=@samples/sample.txt;type=text/plain" \
  -H "Authorization: Bearer <access_token>" \
  http://localhost:8000/api/documents
```

Search ChromaDB for the top matching chunks:

```bash
curl -X POST http://localhost:8000/api/search \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"Where are embeddings stored?\",\"limit\":5}"
```

Ask Gemini a grounded question using retrieved chunks:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"Where are embeddings stored?\",\"limit\":4}"
```

The chat API returns a consistent structured response:

```json
{
  "answer": "...",
  "summary": "...",
  "key_points": ["...", "..."],
  "sources": [
    {
      "document": "Operating Systems.pdf",
      "page": 12
    }
  ],
  "confidence": "High",
  "follow_up_questions": ["...", "..."],
  "citations": [],
  "session_id": "default"
}
```

LLM providers implement the `AnswerGenerator` interface in `backend/app/domain/repositories.py`. Add another provider beside `GeminiAnswerGenerator` and wire it in `backend/app/api/dependencies.py` to swap models without changing the RAG service or routes.

## Useful Commands

Backend:

```bash
uvicorn app.main:app --reload
```

Frontend:

```bash
npm run dev
npm run build
npm run preview
```

Windows helper after installing backend and frontend dependencies:

```powershell
.\scripts\dev.ps1
```

## Next Steps

- Persist documents in Postgres or SQLite.
- Replace the lexical retriever with embeddings and a vector store.
- Add an LLM provider in `AnswerGenerator`.
- Add authentication and per-user document collections.
