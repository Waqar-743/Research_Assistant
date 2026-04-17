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
| **Cache / Pub-Sub** | Redis (Heroku Redis / Upstash) |
| **Observability** | Sentry (FastAPI + Starlette integrations) |
| **Realtime** | WebSocket `/ws/{session_id}` |

## Architecture Overview

```
┌─────────────┐    WebSocket / REST     ┌──────────────┐
│  React App  │ ◄──────────────────────► │  FastAPI API │
│  (Vercel)   │                          │  (Heroku)    │
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

## Deployment

### Recommended Production Stack

| Service | Platform | Notes |
|---------|----------|-------|
| Backend | **Heroku** | Dyno runs `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Frontend | **Vercel** | Auto-deploys from `frontend/` on push |
| Database | **MongoDB Atlas** | Free M0 cluster via GitHub Student Pack |
| Cache | **Heroku Redis** or **Upstash** | Attach as Heroku add-on or separate |
| Monitoring | **Sentry** | Free tier via GitHub Student Pack |

### Heroku Backend Deployment

1. Create a Heroku app and add the **Heroku Redis** add-on.
2. Set config vars:
   ```
   OPENROUTER_API_KEY=...
   MONGODB_URL=mongodb+srv://...
   MONGODB_DATABASE=research_assistant_db
   SENTRY_DSN=https://...
   ```
   `REDIS_URL` is auto-set by the Heroku Redis add-on.
3. Add a `Procfile`:
   ```
   web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
4. Push to Heroku: `git push heroku main`

Once deployed, the backend runs entirely on Heroku — you do **not** run it locally in production. Local execution is only for development.

### GitHub Actions CI/CD Deployments

The repository includes GitHub Actions workflows to automatically deploy the frontend to **GitHub Pages** and the backend to **Heroku**.

1. **Frontend**: Pushes to `main` branch will automatically build and deploy the React app to GitHub Pages. Set `VITE_API_URL` as a repository secret.
2. **Backend**: Pushes to `main` branch will deploy the Docker image to Heroku. You need to configure `HEROKU_API_KEY`, `HEROKU_APP_NAME`, and `HEROKU_EMAIL` as repository secrets.

### Vercel Frontend Deployment (Alternative)

1. Import the repo into Vercel; set **Root Directory** to `frontend`.
2. Set `VITE_API_URL` to your Heroku app URL (e.g. `https://my-app.herokuapp.com`).
3. Vercel auto-builds with `npm run build` on every push.

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

## Contributing

1. Create a branch from `main`
2. Make changes
3. Run tests (`pytest`)
4. Open a Pull Request
