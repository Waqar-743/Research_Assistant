# Multi-Agent Research Assistant

Full-stack research platform with a FastAPI backend and a React + Vite frontend. It orchestrates multiple AI agents for web research, fact-checking, report generation, and document analysis — backed by MongoDB state management, Redis caching/Pub-Sub, and Sentry observability.

## Features

- Multi-agent research workflow (User Proxy, Researcher, Analyst, Fact-Checker, Report Generator, Document Analyzer)
- **MongoDB pipeline state management** — agent outputs persist to the database after each stage; only a `session_id` travels between agents
- **Redis caching** — search results cached for 24 hours with SHA-256 keyed entries, reducing duplicate API calls
- **Redis Pub/Sub** — real-time progress events published and consumed for live status updates
- **Sentry error tracking & performance monitoring** — spans on every LLM call and agent execution, 30 % trace sample rate
- Real-time progress updates via WebSocket
- Document upload and analysis (PDF, DOCX, TXT, MD) with GridFS storage
- Hybrid research (web + uploaded documents)
- Citation extraction and formatting (APA, MLA, Chicago, Harvard)
- Report generation and export support
- User settings API for model and workflow preferences

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | FastAPI · Beanie ODM · Motor · MongoDB Atlas |
| **Frontend** | React 19 · TypeScript · Vite · Tailwind CSS 4 |
| **AI Routing** | OpenRouter (DeepSeek, Claude 3.5 Sonnet, GPT-4o) |
| **Cache / Pub-Sub** | Redis (Render Redis / Upstash) |
| **Observability** | Sentry (FastAPI + Starlette integrations) |
| **Realtime** | WebSocket `/ws/{session_id}` |

## Architecture Overview

```
┌─────────────┐    WebSocket / REST     ┌──────────────┐
│  React App  │ ◄──────────────────────► │  FastAPI API │
│ (GitHub Pages) │                        │  (Render)    │
└─────────────┘                          └──────┬───────┘
                                                │
                          ┌─────────────────────┼─────────────────────┐
                          │                     │                     │
                   ┌──────▼──────┐     ┌────────▼────────┐   ┌───────▼───────┐
                   │  MongoDB    │     │   Redis Cache   │   │    Sentry     │
                   │  Atlas      │     │   + Pub/Sub     │   │  Monitoring   │
                   └─────────────┘     └─────────────────┘   └───────────────┘
```

### Agent Pipeline & State Flow

```
UserProxy ──► Researcher ──► Analyst ──► FactChecker ──► ReportGenerator
                 │               │             │
                 ▼               ▼             ▼
            save sources   save findings   save validated
            to MongoDB     + pipeline_data  findings to
                                           pipeline_data
```

Each agent queries MongoDB by `session_id` to load data from previous stages — no large payloads are passed in memory.

## Agent Architecture

| Agent | Role | LLM Model | Core Responsibility |
|-------|------|-----------|----------------------|
| User Proxy | Orchestrator | — | Coordinates workflow and user-facing control flow |
| Researcher | Discovery | DeepSeek | Collects and filters sources from external providers |
| Analyst | Synthesis | Claude 3.5 Sonnet | Extracts insights, trends, and contradictions |
| Fact-Checker | Validation | GPT-4o | Verifies claims and confidence across evidence |
| Report Generator | Output | DeepSeek | Produces final structured report with citations |
| Document Analyzer | Documents | — | Processes uploaded files and extracts findings |

## Quick Start (Local)

### Prerequisites

- Python 3.11+
- Node.js 20+
- MongoDB 7+ (or MongoDB Atlas)
- Redis (optional — caching degrades gracefully)

### 1) Install backend dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

### 2) Configure environment

```bash
copy .env.example .env
copy frontend\.env.example frontend\.env.local
```

Required variables:

| Variable | Purpose |
|----------|---------|
| `OPENROUTER_API_KEY` | LLM routing via OpenRouter |
| `MONGODB_URL` | MongoDB connection URI |
| `MONGODB_DATABASE` | Database name |
| `REDIS_URL` | Redis connection string (optional) |
| `SENTRY_DSN` | Sentry DSN for error tracking (optional) |

### 3) Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 4) Run backend

```bash
python -m app.main
```

Backend runs at `http://localhost:8000`.

### 5) Run frontend

```bash
cd frontend
npm run dev
```

Frontend runs at `http://localhost:5500`.

### Local links

- Frontend: `http://localhost:5500`
- Backend API: `http://localhost:8000`
- Backend docs: `http://localhost:8000/docs`

If your backend is hosted elsewhere, set `frontend/.env.local`:

```bash
VITE_API_URL=https://your-backend-domain.com
# Optional when websocket host differs from API host
# VITE_WS_URL=wss://your-backend-domain.com
```

## Docker

```bash
# Development
docker compose up -d

# Development + debug profile
docker compose --profile debug up -d

# Production compose
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## API Docs

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Key API Endpoints

### Research

- `POST /api/v1/research/start`
- `GET /api/v1/research/{session_id}`
- `GET /api/v1/research/{session_id}/results`

### Documents

- `POST /api/v1/documents/upload`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `DELETE /api/v1/documents/{document_id}`

### Settings

- `GET /api/v1/settings`
- `PUT /api/v1/settings`
- `DELETE /api/v1/settings`

### Realtime

- `WS /ws/{session_id}`

## Configuration

### All environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FASTAPI_HOST` | Backend host | `0.0.0.0` |
| `FASTAPI_PORT` | Backend port | `8000` |
| `FASTAPI_DEBUG` | Debug/reload mode | `false` |
| `MONGODB_URL` | Mongo connection URI | `mongodb://localhost:27017` |
| `MONGODB_DATABASE` | Database name | `research_assistant_db` |
| `OPENROUTER_API_KEY` | OpenRouter key | _(required)_ |
| `GOOGLE_API_KEY` | Google API key | optional |
| `GOOGLE_SEARCH_ENGINE_ID` | Custom Search Engine ID | optional |
| `SERPAPI_KEY` | SerpAPI key | optional |
| `NEWSAPI_KEY` | News API key | optional |
| `REDIS_URL` | Redis connection URI (`redis://` or `rediss://`) | optional |
| `SENTRY_DSN` | Sentry Data Source Name | optional |

## Testing

```bash
pytest                   # run all 18 tests
pytest tests/ -v         # verbose output
```

## CI Pipeline

GitHub Actions now runs on every push and pull request:

- **Backend Tests**: installs Python dependencies and runs `pytest`
- **Frontend Build**: runs `npm ci`, `npm run lint`, and `npm run build` in `frontend/`

## Deployment

### Recommended Production Stack

| Service | Platform | Notes |
|---------|----------|-------|
| Backend | **Render** | Uses `render.yaml` to run `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Frontend | **GitHub Pages** | Auto-deploys from `frontend/` on push |
| Database | **MongoDB Atlas** | Free M0 cluster via GitHub Student Pack |
| Cache | **Render Redis** or **Upstash** | Managed Redis instance |
| Monitoring | **Sentry** | Free tier via GitHub Student Pack |

### Render Backend Deployment

1. Create a new Render Web Service from this repo and select the `render.yaml` blueprint.
2. Set required env vars in Render:
   ```
   OPENROUTER_API_KEY=...
   MONGODB_URL=mongodb+srv://...
   MONGODB_DATABASE=research_assistant_db
   REDIS_URL=rediss://...
   SENTRY_DSN=https://...
   SECRET_KEY=...
   ```
3. (Optional) Create a Render deploy hook and save it as the GitHub Actions secret `RENDER_DEPLOY_HOOK`.

Once deployed, the backend runs on Render. Local execution is only for development.

### GitHub Pages Frontend Deployment

1. Ensure GitHub Actions is enabled for the repo.
2. Add the GitHub Actions secret `VITE_API_URL` with your Render URL (for example `https://your-service.onrender.com`).
3. Push to `main` to build and deploy to GitHub Pages.

### Live links

| Service | URL |
|---------|-----|
| **Frontend (GitHub Pages)** | https://waqar-743.github.io/Research_Assistant/ |
| **Backend (Render)** | Set up on [Render](https://render.com) using `render.yaml` — see below |

> The frontend is auto-deployed to GitHub Pages on every push to `main`.  
> The backend deploys to Render — see [Render Backend Deployment](#render-backend-deployment) for setup steps.

## Project Structure

```text
Research-Assistant/
├── app/
│   ├── agents/          # AI agent implementations
│   ├── api/
│   │   ├── v1/          # Versioned REST endpoints
│   │   └── websocket.py
│   ├── database/        # Beanie schemas, repositories
│   ├── middleware/       # Error handling, logging
│   ├── models/          # Pydantic models
│   ├── services/        # Research service, Redis cache
│   ├── tools/           # Search, document, LLM tools
│   ├── utils/           # Logging utilities
│   ├── config.py        # Settings (env-driven)
│   └── main.py          # FastAPI entry + Sentry init
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── tests/
├── docker/
├── docker-compose.yml
├── docker-compose.prod.yml
├── Dockerfile
└── requirements.txt
```

## Report Persistence — How It Works

The report follows a two-track persistence strategy so it is never silently lost:

1. **Primary path** — `ReportGenerator` produces a report dict; `ResearchService._save_research_results()` inserts it into the `reports` MongoDB collection as a `Report` document.  `GET /research/{id}/results` reads from this collection via `ReportRepository.get_by_research()`.

2. **Fallback path** — The orchestrator always writes the complete report dict into `ResearchSession.final_report` (a plain `Dict` field on the session document).  If the `Report` collection document is missing (e.g. unique-key collision on a re-run), `GET /research/{id}/results` falls back to building the `ReportResponse` directly from `session.final_report`.

The `Report` collection has `research_id: Indexed(str, unique=True)`.  A re-run of the same session therefore hits a duplicate-key error on insert; the service now detects this and upserts the existing document rather than silently swallowing the failure.

### Pipeline data flow

```
ResearchSession.pipeline_data (MongoDB Dict)
    ├── "researcher_output"    — saved atomically after Researcher finishes
    ├── "analyst_output"       — saved atomically after Analyst finishes
    └── "validated_findings"   — saved atomically after FactChecker finishes

save_pipeline_data() uses dot-notation $set  →  no read-modify-write race
```

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Empty report returned | `Report` insert failed silently on re-run | Upgrade to latest code; upsert logic now handles it |
| `report: null` in API response | `Report` collection missing, no fallback | Upgrade to latest code; fallback reads `session.final_report` |
| Hybrid research 422 error | Wrong field names (`query` vs `search_query`) | Fixed in `start_hybrid_research` endpoint |
| Pipeline data overwritten | Concurrent `save_pipeline_data` race | Fixed to atomic `$set` dot-notation |

## Contributing

1. Create a branch from `main`
2. Make changes
3. Run tests (`pytest`)
4. Open a Pull Request
