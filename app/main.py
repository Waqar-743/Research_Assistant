"""
FastAPI Application Entry Point
Multi-Agent Research Assistant Backend
"""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.config import settings

# -----------------------------------------------------------------
# Phase 3: Sentry — initialised at the very top of the process
# -----------------------------------------------------------------
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        integrations=[FastApiIntegration(), StarletteIntegration()],
        traces_sample_rate=0.3,
        environment="development" if settings.debug else "production",
        send_default_pii=False,
    )

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import research, history, status, health
from app.api.v1 import documents, settings as settings_api
from app.api.websocket import router as websocket_router
from app.database.connection import connect_to_mongo, close_mongo_connection
from app.middleware.error_handler import error_handler_middleware
from app.middleware.logging import logging_middleware
from app.utils.logging import setup_logging, logger
from app.services.redis_cache import get_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup — ensure log directory exists before any file handlers open
    import os as _os
    _os.makedirs("logs", exist_ok=True)

    setup_logging()
    logger.info("Starting Multi-Agent Research Assistant...")
    
    await connect_to_mongo()
    logger.info("Connected to MongoDB")
    
    # Phase 2: Redis
    redis = get_redis()
    await redis.connect()
    logger.info("Connected to Redis")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    await redis.disconnect()
    logger.info("Disconnected from Redis")
    await close_mongo_connection()
    logger.info("Disconnected from MongoDB")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="""
    ## Multi-Agent Research Assistant API
    
    A sophisticated research assistant that leverages multiple AI agents 
    to conduct comprehensive research, answer complex questions, and 
    synthesize information from multiple sources.
    
    ### Features:
    - **Multi-Agent Orchestration**: 5 specialized AI agents working together
    - **Real-time Updates**: WebSocket support for live progress tracking
    - **Multiple Sources**: Google, NewsAPI, ArXiv, PubMed, Wikipedia
    - **Quality Assurance**: Fact-checking and source verification
    - **Report Generation**: Markdown, HTML, and PDF formats
    - **Citation Management**: APA, MLA, Chicago styles
    - **Document Analysis**: Upload and analyze PDFs with AI
    - **Hybrid Research**: Combine web search with document insights
    - **Chat Interface**: Interactive Q&A with research results
    
    ### Agents:
    1. **User Proxy**: Human oversight and feedback
    2. **Researcher**: Search and information gathering
    3. **Analyst**: Information synthesis and analysis
    4. **Fact-Checker**: Validation and verification
    5. **Report Generator**: Report creation and formatting
    6. **Document Analyzer**: Document processing and analysis
    """,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.middleware("http")(error_handler_middleware)
app.middleware("http")(logging_middleware)

# Include API routers
app.include_router(
    health.router,
    prefix="/api/v1/health",
    tags=["Health"]
)

app.include_router(
    research.router,
    prefix="/api/v1/research",
    tags=["Research"]
)

app.include_router(
    history.router,
    prefix="/api/v1/history",
    tags=["History"]
)

app.include_router(
    status.router,
    prefix="/api/v1/status",
    tags=["Status"]
)

# New Document and Settings routers
app.include_router(
    documents.router,
    prefix="/api/v1/documents",
    tags=["Documents"]
)

app.include_router(
    settings_api.router,
    prefix="/api/v1/settings",
    tags=["Settings"]
)

# Include WebSocket router
app.include_router(
    websocket_router,
    prefix="/ws",
    tags=["WebSocket"]
)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint returning API information."""
    return JSONResponse(
        content={
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "running",
            "docs": "/docs",
            "health": "/api/v1/health"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        workers=1 if settings.debug else settings.workers
    )
