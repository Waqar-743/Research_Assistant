"""
Research Service
Main service coordinating the research workflow.

Phase 2: Progress events are also published via Redis Pub/Sub
so that multiple server processes can broadcast to their own
WebSocket clients.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio

from app.agents.orchestrator import AgentOrchestrator
from app.database.schemas import (
    ResearchSession, ResearchStatus, Report
)
from app.database.repositories import (
    ResearchRepository, ReportRepository
)
from app.api.websocket import (
    send_agent_update, send_phase_update,
    send_research_complete, send_research_error,
    manager as ws_manager
)
from app.utils.logging import logger, log_research_progress
from app.services.redis_cache import get_redis


# Global service instance
_research_service: Optional["ResearchService"] = None


def get_research_service() -> "ResearchService":
    """Get the global research service instance."""
    global _research_service
    if _research_service is None:
        _research_service = ResearchService()
    return _research_service


class ResearchService:
    """
    Research Service - Coordinates the entire research workflow.
    
    Responsibilities:
    - Manage research session lifecycle
    - Coordinate with AgentOrchestrator
    - Persist results to database
    - Send real-time updates via WebSocket
    - Handle user feedback for supervised mode
    """
    
    def __init__(self):
        self.active_orchestrators: Dict[str, AgentOrchestrator] = {}
        self.feedback_queues: Dict[str, asyncio.Queue] = {}
    
    async def execute_research(
        self,
        session_id: str,
        query: str,
        focus_areas: Optional[List[str]] = None,
        source_preferences: Optional[List[str]] = None,
        max_sources: int = 300,
        research_mode: str = "auto",
        report_format: str = "markdown",
        citation_style: str = "APA"
    ):
        """
        Execute the complete research workflow.
        
        This is called as a background task from the API endpoint.
        """
        from app.database.schemas import ResearchSession as _RS

        logger.info(f"Starting research execution for session {session_id}")
        
        # Update session status
        session = await ResearchRepository.get_by_session_id(session_id)
        if session:
            session.status = ResearchStatus.RUNNING
            session.updated_at = datetime.utcnow()
            await session.save()
        
        # Create orchestrator
        orchestrator = AgentOrchestrator()
        self.active_orchestrators[session_id] = orchestrator
        
        # Set up progress callback for WebSocket updates
        # Track each agent's progress locally so we can compute a
        # monotonically-increasing overall_progress in every WS message.
        _local_agent_statuses: Dict[str, Any] = {}
        _agent_weights = {
            "user_proxy": 10,
            "researcher": 30,
            "analyst": 25,
            "fact_checker": 20,
            "report_generator": 15
        }

        async def progress_callback(
            agent_name: str,
            status: str,
            progress: int,
            output: Optional[str] = None,
            error: Optional[str] = None
        ):
            # Keep a local snapshot of every named agent
            if agent_name in _agent_weights:
                _local_agent_statuses[agent_name] = {
                    "status": status,
                    "progress": progress
                }

            # Compute weighted overall progress (same formula as DB layer)
            overall = 0
            for _name, _weight in _agent_weights.items():
                _state = _local_agent_statuses.get(_name, {})
                if _state.get("status") == "completed":
                    overall += _weight
                elif _state.get("status") == "in_progress":
                    overall += int(_weight * (_state.get("progress", 0) / 100))
            overall_progress = min(overall, 100)

            # ── Phase 2: Publish to Redis Pub/Sub ─────────────────
            redis = get_redis()
            await redis.publish_progress(session_id, {
                "agent": agent_name,
                "status": status,
                "progress": progress,
                "overall_progress": overall_progress,
                "output": output,
                "error": error,
            })
            # ──────────────────────────────────────────────────────

            # Send WebSocket update — include overall_progress in data so the
            # frontend never needs to guess which progress value is "pipeline-wide"
            await send_agent_update(
                session_id=session_id,
                agent_name=agent_name,
                status=status,
                progress=progress,
                output=output,
                error=error,
                data={"overall_progress": overall_progress}
            )
            
            # Update database
            await self._update_session_progress(
                session_id, agent_name, status, progress, output, error
            )
            
            # Log progress
            log_research_progress(session_id, agent_name, progress, output)
        
        orchestrator.set_progress_callback(progress_callback)
        
        try:
            # Send phase update
            await send_phase_update(session_id, "initialization", "started")
            
            # Execute research
            results = await orchestrator.execute(
                session_id=session_id,
                query=query,
                focus_areas=focus_areas,
                source_preferences=source_preferences,
                max_sources=max_sources,
                research_mode=research_mode,
                report_format=report_format,
                citation_style=citation_style
            )
            
            if results.get("status") == "completed":
                # Save results to database
                await self._save_research_results(session_id, results)
                
                # Update session as completed using atomic $set
                await _RS.find_one(
                    _RS.research_id == session_id
                ).update({"$set": {
                    "status": ResearchStatus.COMPLETED,
                    "progress": 100,
                    "completed_at": datetime.utcnow(),
                    "final_report": results.get("report", {}),
                    "sources_count": results.get("sources_count", {}),
                    "findings_count": len(results.get("findings", [])),
                    "confidence_summary": results.get("confidence_summary", {}),
                }})
                
                # Send completion notification
                await send_research_complete(session_id, results)
                
                logger.info(f"Research completed successfully for session {session_id}")
                
            elif results.get("status") == "failed":
                # Update session as failed using atomic $set
                await _RS.find_one(
                    _RS.research_id == session_id
                ).update({"$set": {
                    "status": ResearchStatus.FAILED,
                    "error_message": results.get("error", "Unknown error"),
                }})
                
                # Send error notification
                await send_research_error(
                    session_id,
                    results.get("error", "Research failed"),
                    results.get("phase")
                )
                
                logger.error(f"Research failed for session {session_id}: {results.get('error')}")
            
            elif results.get("status") == "cancelled":
                await _RS.find_one(
                    _RS.research_id == session_id
                ).update({"$set": {
                    "status": ResearchStatus.CANCELLED,
                }})
                
                logger.info(f"Research cancelled for session {session_id}")
            
        except Exception as e:
            logger.error(f"Research execution error: {e}")
            
            # Update session as failed using atomic $set
            try:
                await _RS.find_one(
                    _RS.research_id == session_id
                ).update({"$set": {
                    "status": ResearchStatus.FAILED,
                    "error_message": str(e),
                }})
            except Exception:
                logger.warning("Failed to update session status on error")
            
            await send_research_error(session_id, str(e))
            
        finally:
            # Clean up
            if session_id in self.active_orchestrators:
                del self.active_orchestrators[session_id]
    
    async def _update_session_progress(
        self,
        session_id: str,
        agent_name: str,
        status: str,
        progress: int,
        output: Optional[str],
        error: Optional[str]
    ):
        """Update session progress in database using atomic $set to avoid overwriting pipeline_data."""
        try:
            from app.database.schemas import ResearchSession

            session = await ResearchRepository.get_by_session_id(session_id)
            if session:
                if session.agent_statuses is None:
                    session.agent_statuses = {}

                session.agent_statuses[agent_name] = {
                    "status": status,
                    "progress": progress,
                    "output": output[:500] if output else None,
                    "error": error,
                    "updated_at": datetime.utcnow().isoformat()
                }

                agent_weights = {
                    "user_proxy": 10,
                    "researcher": 30,
                    "analyst": 25,
                    "fact_checker": 20,
                    "report_generator": 15
                }

                overall = 0
                for agent, weight in agent_weights.items():
                    agent_status = session.agent_statuses.get(agent, {})
                    if agent_status.get("status") == "completed":
                        overall += weight
                    elif agent_status.get("status") == "in_progress":
                        overall += int(weight * (agent_status.get("progress", 0) / 100))

                overall_progress = min(overall, 100)

                # Use atomic $set instead of session.save() to avoid
                # overwriting pipeline_data that may have been updated
                # concurrently by save_pipeline_data().
                await ResearchSession.find_one(
                    ResearchSession.research_id == session_id
                ).update({"$set": {
                    "agent_statuses": session.agent_statuses,
                    "current_phase": agent_name,
                    "progress": overall_progress,
                    "updated_at": datetime.utcnow(),
                }})

        except Exception as e:
            logger.warning(f"Failed to update session progress: {e}")
    
    async def _save_research_results(
        self,
        session_id: str,
        results: Dict[str, Any]
    ):
        """
        Save research results to database.

        Phase 1: sources and findings are already persisted by the
        orchestrator during the pipeline.  This method now only
        persists the **report** (to avoid double-inserting sources
        and findings).
        """
        report_data = results.get("report", {})
        if not report_data:
            logger.warning(f"No report_data to save for session {session_id}")
            return

        try:
            report = Report(
                research_id=session_id,
                title=report_data.get("title") or "",
                summary=report_data.get("summary") or "",
                markdown_content=report_data.get("markdown_content") or "",
                html_content=report_data.get("html_content") or None,
                sections=report_data.get("sections") or [],
                citation_style=report_data.get("citation_style") or "APA",
                quality_score=float(report_data.get("quality_score") or 0),
                generated_at=datetime.utcnow()
            )
            await report.insert()
            logger.info(f"Saved report for session {session_id}")

        except Exception as insert_err:
            # Insert failed (e.g. duplicate key on re-run). Attempt upsert.
            logger.warning(
                f"Report insert failed for session {session_id} ({insert_err}), "
                f"attempting update of existing report..."
            )
            try:
                existing = await Report.find_one(Report.research_id == session_id)
                if existing:
                    await existing.update({"$set": {
                        "title": report_data.get("title") or "",
                        "summary": report_data.get("summary") or "",
                        "markdown_content": report_data.get("markdown_content") or "",
                        "html_content": report_data.get("html_content") or None,
                        "sections": report_data.get("sections") or [],
                        "quality_score": float(report_data.get("quality_score") or 0),
                    }})
                    logger.info(f"Updated existing report for session {session_id}")
                else:
                    logger.error(
                        f"Report could not be saved for session {session_id}: "
                        f"insert failed and no existing document found. Error: {insert_err}"
                    )
            except Exception as upsert_err:
                logger.error(
                    f"Failed to save/update report for session {session_id}: {upsert_err}"
                )
    
    async def cancel_research(self, session_id: str):
        """Cancel an in-progress research session."""
        if session_id in self.active_orchestrators:
            orchestrator = self.active_orchestrators[session_id]
            await orchestrator.cancel()
            logger.info(f"Cancelled research for session {session_id}")
    
    async def process_feedback(
        self,
        session_id: str,
        approved: bool,
        feedback: str,
        modifications: Optional[Dict[str, Any]] = None
    ):
        """Process user feedback for supervised mode."""
        logger.info(f"Processing feedback for session {session_id}: approved={approved}")
        
        if session_id in self.active_orchestrators:
            orchestrator = self.active_orchestrators[session_id]
            
            # Pass feedback to user proxy agent
            if hasattr(orchestrator, 'user_proxy'):
                await orchestrator.user_proxy.receive_feedback(
                    feedback=feedback,
                    approved=approved,
                    modifications=modifications
                )
    
    def get_active_sessions(self) -> List[str]:
        """Get list of active session IDs."""
        return list(self.active_orchestrators.keys())
    
    def is_session_active(self, session_id: str) -> bool:
        """Check if a session is currently active."""
        return session_id in self.active_orchestrators
