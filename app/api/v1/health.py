"""
Health Check API Endpoints
System health and readiness checks.
"""

from fastapi import APIRouter
from datetime import datetime

from app.models import APIResponse
from app.database.connection import check_database_connection, db as _mongo_db
from app.config import settings
from app.utils.logging import logger


router = APIRouter()


@router.get("/", response_model=APIResponse)
async def health_check():
    """
    Basic health check endpoint.
    Returns OK if the service is running.
    """
    return APIResponse(
        status=200,
        message="Service is healthy",
        data={
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "1.0.0"
        }
    )


@router.get("/ready", response_model=APIResponse)
async def readiness_check():
    """
    Readiness check - verifies all dependencies are available.
    """
    try:
        checks = {
            "database": False,
            "openrouter_api": False
        }
        
        # Check database connection
        try:
            db_ok = await check_database_connection()
            checks["database"] = db_ok
        except Exception as e:
            logger.warning(f"Database check failed: {e}")
            checks["database"] = False
        
        # Check OpenRouter API key is configured
        checks["openrouter_api"] = bool(settings.openrouter_api_key)
        
        # Overall readiness
        is_ready = all(checks.values())
        
        return APIResponse(
            status=200 if is_ready else 503,
            message="Service is ready" if is_ready else "Service not ready",
            data={
                "ready": is_ready,
                "checks": checks,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return APIResponse(
            status=500,
            message="Readiness check failed",
            data={
                "ready": False,
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )


@router.get("/live", response_model=APIResponse)
async def liveness_check():
    """
    Liveness check — basic check that the service is running.
    Also reports whether the database connection is established so the
    frontend can show a meaningful status without a separate call.
    """
    db_connected = _mongo_db.database is not None
    data: dict = {
        "alive": True,
        "db_connected": db_connected,
        "timestamp": datetime.utcnow().isoformat(),
    }
    if not db_connected and _mongo_db.connect_error:
        data["db_error"] = _mongo_db.connect_error
    return APIResponse(status=200, message="Service is alive", data=data)


@router.get("/info", response_model=APIResponse)
async def service_info():
    """
    Get service information and configuration (non-sensitive).
    """
    return APIResponse(
        status=200,
        message="Service information retrieved",
        data={
            "service": "Multi-Agent Research Assistant",
            "version": "1.0.0",
            "debug_mode": settings.debug,
            "api_version": "v1",
            "supported_formats": ["markdown", "html", "pdf"],
            "supported_citation_styles": ["APA", "MLA", "Chicago"],
            "agents": [
                "User Proxy",
                "Researcher",
                "Analyst",
                "Fact-Checker",
                "Report Generator"
            ],
            "data_sources": [
                "SerpAPI",
                "NewsAPI",
                "ArXiv",
                "PubMed",
                "Wikipedia"
            ]
        }
    )
