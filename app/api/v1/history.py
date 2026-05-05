"""
History API Endpoints
Endpoints for retrieving past research sessions.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime

from app.models import APIResponse
from app.database.schemas import ResearchSession, ResearchStatus
from app.database.repositories import ResearchRepository
from app.utils.logging import logger


router = APIRouter()


@router.get("/", response_model=APIResponse)
async def list_research_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in query text")
):
    """
    List all research sessions with pagination.
    """
    try:
        skip = (page - 1) * limit

        # Build filter
        status_filter = None
        if status:
            try:
                status_filter = ResearchStatus(status)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

        # Get sessions with pagination — gracefully degrade if DB unavailable
        try:
            sessions = await ResearchRepository.list_sessions(
                skip=skip,
                limit=limit,
                status_filter=status_filter,
                search_query=search
            )
            total_count = await ResearchRepository.count_sessions(
                status_filter=status_filter,
                search_query=search
            )
        except Exception as db_err:
            logger.error(f"History DB query failed: {db_err}", exc_info=True)
            sessions = []
            total_count = 0

        # Format response — skip any session that fails to serialize
        session_list = []
        for s in sessions:
            try:
                session_list.append({
                    "session_id": s.research_id,
                    "query": s.query,
                    "status": s.status.value if s.status else "unknown",
                    "progress": s.progress or 0,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                    "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                    "research_mode": s.research_mode.value if s.research_mode else "auto",
                })
            except Exception as serial_err:
                logger.warning(f"Skipping malformed session: {serial_err}")

        return APIResponse(
            status=200,
            message="History retrieved successfully",
            data={
                "sessions": session_list,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_count,
                    "pages": max(1, (total_count + limit - 1) // limit),
                },
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list history: {str(e)}")


@router.get("/{session_id}", response_model=APIResponse)
async def get_session_details(session_id: str):
    """
    Get detailed information about a specific research session.
    """
    try:
        session = await ResearchRepository.get_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Research session {session_id} not found"
            )
        
        # Build detailed response
        session_detail = {
            "session_id": session.research_id,
            "query": session.query,
            "status": session.status.value,
            "progress": session.progress or 0,
            "current_phase": session.current_phase or session.current_stage,
            "research_mode": session.research_mode.value if session.research_mode else "auto",
            "focus_areas": session.focus_areas or [],
            "source_preferences": session.source_preferences or [],
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "agent_statuses": session.agent_statuses or {},
            "sources_count": session.sources_count or {},
            "findings_count": session.findings_count or session.total_findings or 0,
            "confidence_summary": session.confidence_summary or {},
            "error_message": session.error_message or session.error
        }
        
        return APIResponse(
            status=200,
            message="Session details retrieved successfully",
            data=session_detail
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session details: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session details: {str(e)}"
        )


@router.delete("/{session_id}", response_model=APIResponse)
async def delete_session(session_id: str):
    """
    Delete a research session and its associated data.
    """
    try:
        session = await ResearchRepository.get_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Research session {session_id} not found"
            )
        
        # Delete the session
        await ResearchRepository.delete(session_id)
        
        return APIResponse(
            status=200,
            message="Session deleted successfully",
            data={"session_id": session_id}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete session: {str(e)}"
        )


@router.get("/{session_id}/sources", response_model=APIResponse)
async def get_session_sources(
    session_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get sources collected for a research session.
    """
    try:
        from app.database.repositories import SourceRepository
        
        session = await ResearchRepository.get_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Research session {session_id} not found"
            )
        
        skip = (page - 1) * limit
        
        all_sources = await SourceRepository.get_by_research(research_id=session_id)
        sources = all_sources[skip:skip + limit]
        
        source_list = [
            {
                "id": str(s.id),
                "title": s.title,
                "url": s.url,
                "api_source": s.api_source,
                "source_type": s.source_type.value if s.source_type else None,
                "credibility_score": s.credibility_score,
                "snippet": (s.content_preview or "")[:200] if s.content_preview else None
            }
            for s in sources
        ]
        
        return APIResponse(
            status=200,
            message="Sources retrieved successfully",
            data={
                "session_id": session_id,
                "sources": source_list,
                "count": len(source_list)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get sources: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sources: {str(e)}"
        )


@router.get("/{session_id}/findings", response_model=APIResponse)
async def get_session_findings(
    session_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get findings for a research session.
    """
    try:
        from app.database.repositories import FindingRepository
        
        session = await ResearchRepository.get_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Research session {session_id} not found"
            )
        
        skip = (page - 1) * limit
        
        all_findings = await FindingRepository.get_by_research(research_id=session_id)
        findings = all_findings[skip:skip + limit]
        
        finding_list = [
            {
                "id": str(f.id),
                "title": f.title,
                "content": f.content,
                "finding_type": f.finding_type.value if f.finding_type else None,
                "confidence_score": f.confidence_score,
                "verified": f.verified
            }
            for f in findings
        ]
        
        return APIResponse(
            status=200,
            message="Findings retrieved successfully",
            data={
                "session_id": session_id,
                "findings": finding_list,
                "count": len(finding_list)
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get findings: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get findings: {str(e)}"
        )


@router.get("/{session_id}/report", response_model=APIResponse)
async def get_session_report(session_id: str, format: str = Query("markdown")):
    """
    Get the generated report for a research session.
    """
    try:
        from app.database.repositories import ReportRepository
        
        session = await ResearchRepository.get_by_id(session_id)
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail=f"Research session {session_id} not found"
            )
        
        report = await ReportRepository.get_by_research(research_id=session_id)
        
        if not report:
            return APIResponse(
                status=200,
                message="Report not yet generated",
                data={"session_id": session_id, "report_status": session.status.value}
            )
        
        # Return content based on requested format
        content = None
        if format == "markdown":
            content = report.markdown_content
        elif format == "html":
            content = report.html_content
        else:
            content = report.markdown_content
        
        return APIResponse(
            status=200,
            message="Report retrieved successfully",
            data={
                "session_id": session_id,
                "title": report.title,
                "summary": report.summary,
                "content": content,
                "format": format,
                "citation_style": report.citation_style,
                "quality_score": report.quality_score,
                "generated_at": report.generated_at.isoformat() if report.generated_at else None
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get report: {str(e)}"
        )


