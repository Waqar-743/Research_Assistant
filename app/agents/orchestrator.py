"""
Agent Orchestrator
Coordinates the multi-agent research workflow.

Phase 1 refactor: agents no longer pass raw text payloads through the
``final_context`` dict.  After each agent completes, its output is
persisted to MongoDB and subsequent agents receive only the session_id.
"""

from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from enum import Enum
import asyncio

import sentry_sdk

from app.agents.base_agent import AgentStatus
from app.agents.researcher import ResearcherAgent
from app.agents.analyst import AnalystAgent
from app.agents.fact_checker import FactCheckerAgent
from app.agents.report_generator import ReportGeneratorAgent
from app.agents.user_proxy import UserProxyAgent
from app.config import settings
from app.utils.logging import logger
from app.database.repositories import (
    ResearchRepository, SourceRepository, FindingRepository
)
from app.database.schemas import SourceType


class WorkflowPhase(str, Enum):
    """Workflow execution phases."""
    INITIALIZATION = "initialization"
    QUERY_PROCESSING = "query_processing"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    FACT_CHECKING = "fact_checking"
    REPORT_GENERATION = "report_generation"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentOrchestrator:
    """
    Agent Orchestrator - Coordinates multi-agent research workflow.
    
    Workflow Sequence:
    1. User Proxy: Clarify query and get approval (if supervised)
    2. Researcher: Gather information from multiple sources
    3. Analyst: Synthesize and analyze findings
    4. Fact-Checker: Verify claims and assess credibility
    5. Report Generator: Create comprehensive research report
    
    Supports:
    - Auto mode: Full autonomous execution
    - Supervised mode: Checkpoints for human approval
    - Real-time progress updates via WebSocket
    """
    
    def __init__(self):
        """Initialize the orchestrator and all agents."""
        self.session_id: Optional[str] = None
        self.current_phase = WorkflowPhase.INITIALIZATION
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        
        # Initialize all agents
        self.user_proxy = UserProxyAgent()
        self.researcher = ResearcherAgent()
        self.analyst = AnalystAgent()
        self.fact_checker = FactCheckerAgent()
        self.report_generator = ReportGeneratorAgent()
        
        # Callback for progress updates
        self._progress_callback: Optional[Callable] = None
        
        # Execution state
        self.is_running = False
        self.is_cancelled = False
        self.results: Dict[str, Any] = {}
        self.errors: List[str] = []
    
    def set_progress_callback(self, callback: Callable):
        """
        Set callback for real-time progress updates.
        
        Callback signature:
        async def callback(
            agent_name: str,
            status: str,
            progress: int,
            output: Optional[str] = None,
            error: Optional[str] = None
        )
        """
        self._progress_callback = callback
        
        # Set callback on all agents
        self.user_proxy.set_progress_callback(callback)
        self.researcher.set_progress_callback(callback)
        self.analyst.set_progress_callback(callback)
        self.fact_checker.set_progress_callback(callback)
        self.report_generator.set_progress_callback(callback)
    
    async def _notify_progress(
        self,
        agent_name: str,
        status: str,
        progress: int,
        output: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Send progress notification."""
        if self._progress_callback:
            await self._progress_callback(
                agent_name=agent_name,
                status=status,
                progress=progress,
                output=output,
                error=error
            )
    
    async def execute(
        self,
        session_id: str,
        query: str,
        focus_areas: Optional[List[str]] = None,
        source_preferences: Optional[List[str]] = None,
        max_sources: int = 50,
        research_mode: str = "auto",
        report_format: str = "markdown",
        citation_style: str = "APA"
    ) -> Dict[str, Any]:
        """
        Execute the complete research workflow.
        
        Args:
            session_id: Unique session identifier
            query: Research query
            focus_areas: Specific areas to focus on
            source_preferences: Preferred source types
            max_sources: Maximum sources to collect
            research_mode: "auto" or "supervised"
            report_format: "markdown", "html", or "pdf"
            citation_style: "APA", "MLA", or "Chicago"
            
        Returns:
            Complete research results including report
        """
        self.session_id = session_id
        self.started_at = datetime.utcnow()
        self.is_running = True
        self.is_cancelled = False
        self.results = {}
        self.errors = []
        
        logger.info(f"Starting research workflow for session {session_id}: {query}")
        
        context = {
            "query": query,
            "focus_areas": focus_areas or [],
            "source_preferences": source_preferences or [],
            "max_sources": max_sources,
            "research_mode": research_mode,
            "report_format": report_format,
            "citation_style": citation_style
        }
        
        try:
            # Phase 1: Query Processing (User Proxy)
            self.current_phase = WorkflowPhase.QUERY_PROCESSING
            await self._notify_progress(
                "orchestrator", "in_progress", 5,
                "Phase 1: Processing research query..."
            )
            
            user_proxy_result = await self._execute_agent(
                self.user_proxy, context, "user_proxy"
            )
            
            if not user_proxy_result.get("approved"):
                return await self._handle_rejection(user_proxy_result)
            
            # Update context with clarified query
            final_context = user_proxy_result.get("final_context", context)

            # SAFEGUARD: always preserve the user's original query.
            # The UserProxy may have placed a clarified version in
            # final_context["query"].  Overwrite with the original so
            # every downstream agent works on the topic the user typed.
            final_context["query"] = query
            logger.info(
                f"Orchestrator query safeguard: using original='{query}'"
            )

            self.results["user_proxy"] = user_proxy_result
            
            # Phase 2: Research (Researcher)
            self.current_phase = WorkflowPhase.RESEARCH
            await self._notify_progress(
                "orchestrator", "in_progress", 20,
                "Phase 2: Gathering information..."
            )
            
            researcher_result = await self._execute_agent(
                self.researcher, final_context, "researcher"
            )
            
            if researcher_result.get("status") == "failed":
                return await self._handle_failure("researcher", researcher_result)
            
            self.results["researcher"] = researcher_result

            # ── Phase 1 state management ──────────────────────────────
            # Persist sources + raw findings to MongoDB; do NOT put them
            # into final_context so downstream agents query the DB.
            persist_stats = await self._persist_researcher_output(session_id, researcher_result)
            # Verify sources actually landed in MongoDB
            source_count = await SourceRepository.count_by_research(session_id)
            finding_count = await FindingRepository.count_by_research(session_id)
            extracted_count = len(researcher_result.get("raw_findings", []))
            logger.info(
                f"Researcher persistence check: extracted={extracted_count}, "
                f"persisted_findings={finding_count}, persisted_sources={source_count}, "
                f"persist_stats={persist_stats}"
            )

            if extracted_count > 0 and finding_count == 0:
                logger.warning(
                    "Findings were extracted but none persisted to DB; retrying finding persistence once"
                )
                sentry_sdk.capture_message(
                    f"Findings persistence mismatch for session {session_id}: extracted={extracted_count}, persisted=0",
                    level="warning",
                )
                persist_stats = await self._persist_researcher_output(session_id, researcher_result)
                finding_count = await FindingRepository.count_by_research(session_id)
                logger.info(
                    f"Post-retry findings persistence: persisted_findings={finding_count}, "
                    f"persist_stats={persist_stats}"
                )
            if source_count == 0:
                logger.warning("0 sources persisted after researcher run — retrying with broadened query")
                sentry_sdk.capture_message(
                    f"0 sources persisted for session {session_id}, retrying with broader query",
                    level="warning",
                )
                await self._notify_progress(
                    "researcher", "in_progress", 30,
                    "No sources found — retrying with a broader search…"
                )
                # Build a broader retry context
                retry_context = {**final_context}
                retry_context["query"] = f"{query} overview research analysis"
                retry_context["max_sources"] = max(max_sources, 100)
                retry_result = await self._execute_agent(
                    self.researcher, retry_context, "researcher"
                )
                if retry_result.get("status") != "failed":
                    self.results["researcher"] = retry_result
                    researcher_result = retry_result
                    await self._persist_researcher_output(session_id, retry_result)
                    source_count = await SourceRepository.count_by_research(session_id)
                    logger.info(f"Retry persisted {source_count} sources")
                else:
                    logger.error("Retry also failed — continuing with 0 sources")
            # Lightweight refs travel in context; also keep raw_findings
            # as fallback data for downstream agents when DB loading fails.
            final_context["session_id"] = session_id
            final_context["sources_count"] = researcher_result.get("sources_count", {})
            final_context["raw_findings"] = researcher_result.get("raw_findings", [])
            final_context["sources"] = researcher_result.get("sources", [])
            # ──────────────────────────────────────────────────────────
            
            # Supervised checkpoint after research
            if research_mode == "supervised":
                await self._checkpoint("research_complete", researcher_result)
            
            # Phase 3: Analysis (Analyst)
            self.current_phase = WorkflowPhase.ANALYSIS
            await self._notify_progress(
                "orchestrator", "in_progress", 45,
                "Phase 3: Analyzing findings..."
            )
            
            analyst_result = await self._execute_agent(
                self.analyst, final_context, "analyst"
            )
            
            if analyst_result.get("status") == "failed":
                return await self._handle_failure("analyst", analyst_result)
            
            self.results["analyst"] = analyst_result

            # ── Phase 1 state management ──────────────────────────────
            await self._persist_analyst_output(session_id, analyst_result)
            # ──────────────────────────────────────────────────────────
            
            # Supervised checkpoint after analysis
            if research_mode == "supervised":
                await self._checkpoint("analysis_complete", analyst_result)
            
            # Phase 4: Fact-Checking (Fact-Checker)
            self.current_phase = WorkflowPhase.FACT_CHECKING
            await self._notify_progress(
                "orchestrator", "in_progress", 65,
                "Phase 4: Verifying facts..."
            )
            
            fact_checker_result = await self._execute_agent(
                self.fact_checker, final_context, "fact_checker"
            )
            
            if fact_checker_result.get("status") == "failed":
                # Non-critical failure - pass through unverified findings so report still has data
                logger.warning("Fact-checking failed, continuing with unverified data")
                self.errors.append("Fact-checking incomplete")
                
                # Persist a fallback confidence_summary so report_generator can load it
                await ResearchRepository.save_pipeline_data(
                    session_id, "confidence_summary", {
                        "overall_confidence": 0.5,
                        "confidence_level": "medium",
                        "verified_findings": 0,
                        "total_findings": 0,
                        "note": "Fact-checking failed; findings are unverified"
                    }
                )
            else:
                self.results["fact_checker"] = fact_checker_result
                
                # ── Phase 1 state management ──────────────────────────
                await self._persist_fact_checker_output(session_id, fact_checker_result)
                # ──────────────────────────────────────────────────────
            
            # Phase 5: Report Generation (Report Generator)
            self.current_phase = WorkflowPhase.REPORT_GENERATION
            await self._notify_progress(
                "orchestrator", "in_progress", 85,
                "Phase 5: Generating report..."
            )
            
            report_result = await self._execute_agent(
                self.report_generator, final_context, "report_generator"
            )
            
            if report_result.get("status") == "failed":
                return await self._handle_failure("report_generator", report_result)
            
            self.results["report_generator"] = report_result
            
            # Complete
            self.current_phase = WorkflowPhase.COMPLETED
            self.completed_at = datetime.utcnow()
            self.is_running = False
            
            await self._notify_progress(
                "orchestrator", "completed", 100,
                "Research completed successfully!"
            )
            
            return self._build_final_response()
            
        except asyncio.CancelledError:
            logger.info(f"Research cancelled for session {session_id}")
            self.is_cancelled = True
            self.is_running = False
            self.current_phase = WorkflowPhase.FAILED
            return {
                "status": "cancelled",
                "session_id": session_id,
                "message": "Research was cancelled by user"
            }
            
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            self.current_phase = WorkflowPhase.FAILED
            self.is_running = False
            return {
                "status": "failed",
                "session_id": session_id,
                "error": str(e),
                "phase": self.current_phase.value
            }
    
    async def _execute_agent(
        self,
        agent,
        context: Dict[str, Any],
        agent_key: str
    ) -> Dict[str, Any]:
        """Execute a single agent with error handling and Sentry context."""
        
        if self.is_cancelled:
            raise asyncio.CancelledError()
        
        # Phase 3: Sentry span + tag for per-agent tracing
        with sentry_sdk.start_span(op="agent.execute", description=agent.name) as span:
            span.set_data("agent", agent_key)
            span.set_data("session_id", self.session_id)
            sentry_sdk.set_tag("agent", agent_key)
            sentry_sdk.set_tag("session_id", self.session_id)

            try:
                agent.reset()
                result = await asyncio.wait_for(
                    agent.execute(context),
                    timeout=agent.timeout
                )
                return result
                
            except asyncio.TimeoutError:
                logger.error(f"Agent {agent.name} timed out")
                sentry_sdk.capture_message(f"Agent {agent.name} timed out", level="warning")
                await self._notify_progress(
                    agent_key, "failed", 0,
                    error=f"{agent.name} timed out"
                )
                return {
                    "status": "failed",
                    "error": f"{agent.name} execution timed out"
                }
            except Exception as e:
                logger.error(f"Agent {agent.name} failed: {e}")
                sentry_sdk.capture_exception(e)
                await self._notify_progress(
                    agent_key, "failed", 0,
                    error=str(e)
                )
                return {
                    "status": "failed",
                    "error": str(e)
                }
    
    async def _checkpoint(self, checkpoint_name: str, data: Dict[str, Any]):
        """Handle checkpoint in supervised mode."""
        
        logger.info(f"Checkpoint: {checkpoint_name}")
        
        await self._notify_progress(
            "orchestrator", "awaiting_approval", 0,
            f"Checkpoint: {checkpoint_name}. Awaiting approval..."
        )
        
        # In a full implementation, this would wait for user approval
        # For now, we auto-continue after a brief pause
        await asyncio.sleep(0.5)
    
    async def _handle_rejection(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle research rejection."""
        
        self.current_phase = WorkflowPhase.FAILED
        self.is_running = False
        
        return {
            "status": "rejected",
            "session_id": self.session_id,
            "message": result.get("message", "Research not approved"),
            "started_at": self.started_at.isoformat() if self.started_at else None
        }
    
    async def _handle_failure(
        self,
        agent_name: str,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle agent failure."""
        
        self.current_phase = WorkflowPhase.FAILED
        self.is_running = False
        
        error_msg = result.get("error", "Unknown error")
        self.errors.append(f"{agent_name}: {error_msg}")
        
        await self._notify_progress(
            "orchestrator", "failed", 0,
            error=f"Research failed at {agent_name}: {error_msg}"
        )
        
        return {
            "status": "failed",
            "session_id": self.session_id,
            "phase": self.current_phase.value,
            "failed_at": agent_name,
            "error": error_msg,
            "partial_results": self.results
        }
    
    # =================================================================
    # Phase 1: MongoDB persistence helpers — save agent outputs to DB
    # =================================================================
    async def _persist_researcher_output(
        self, session_id: str, result: Dict[str, Any]
    ) -> Dict[str, int]:
        """Save sources and raw findings to MongoDB after researcher completes."""
        try:
            sources = result.get("sources", [])
            raw_findings = result.get("raw_findings", [])
            existing_source_count = await SourceRepository.count_by_research(session_id)
            existing_finding_count = await FindingRepository.count_by_research(session_id)

            # Bulk-insert source documents
            source_dicts = []
            for s in sources[:200]:
                source_dicts.append({
                    "research_id": session_id,
                    "title": s.get("title", ""),
                    "url": s.get("url", ""),
                    "content_preview": s.get("snippet", "") or s.get("description", ""),
                    "api_source": s.get("api_source", "unknown"),
                    "source_type": self._map_source_type(s.get("source_type")),
                    "author": s.get("author"),
                    "published_at": s.get("published_at"),
                    "metadata": s,
                })
            if source_dicts:
                await SourceRepository.create_many(source_dicts)

            # Build finding documents
            finding_dicts = []
            for f in raw_findings:
                content = f.get("content", "")
                if not content:
                    continue
                finding_dicts.append({
                    "research_id": session_id,
                    "title": content[:80] if content else "Finding",
                    "content": content,
                    "finding_type": "insight",
                    "agent_generated_by": "researcher",
                    "metadata": {
                        "source_refs": f.get("source_refs", ""),
                        "resolved_sources": f.get("resolved_sources", []),
                        "preliminary_credibility": f.get("preliminary_credibility", "medium"),
                    },
                })
            if finding_dicts:
                try:
                    await FindingRepository.create_many(finding_dicts)
                except Exception as bulk_err:
                    # Bulk insert failed (e.g. schema validation) — insert one by one
                    logger.warning(
                        f"Bulk finding insert failed ({bulk_err}), falling back to per-item insert"
                    )
                    for fd in finding_dicts:
                        try:
                            await FindingRepository.create(fd)
                        except Exception as single_err:
                            logger.warning(f"Single finding insert failed: {single_err}")

            persisted_source_count = await SourceRepository.count_by_research(session_id)
            persisted_finding_count = await FindingRepository.count_by_research(session_id)

            # Update session metrics
            await ResearchRepository.update_metrics(
                session_id,
                total_sources=len(source_dicts),
                total_findings=len(finding_dicts),
            )
            logger.info(
                f"Persisted researcher output: {len(source_dicts)} sources, "
                f"{len(finding_dicts)} findings "
                f"(db delta: +{persisted_source_count - existing_source_count} sources, "
                f"+{persisted_finding_count - existing_finding_count} findings)"
            )
            return {
                "attempted_sources": len(source_dicts),
                "attempted_findings": len(finding_dicts),
                "db_sources_before": existing_source_count,
                "db_findings_before": existing_finding_count,
                "db_sources_after": persisted_source_count,
                "db_findings_after": persisted_finding_count,
            }
        except Exception as e:
            logger.error(f"Failed to persist researcher output: {e}")
            sentry_sdk.capture_exception(e)
            return {
                "attempted_sources": 0,
                "attempted_findings": 0,
                "db_sources_before": 0,
                "db_findings_before": 0,
                "db_sources_after": 0,
                "db_findings_after": 0,
            }

    async def _persist_analyst_output(
        self, session_id: str, result: Dict[str, Any]
    ):
        """Save analyst intermediate results to pipeline_data in MongoDB."""
        try:
            for key in ("organized_findings", "patterns", "key_insights", "contradictions"):
                value = result.get(key, [])
                if value:
                    await ResearchRepository.save_pipeline_data(session_id, key, value)
            logger.info("Persisted analyst output to pipeline_data")
        except Exception as e:
            logger.error(f"Failed to persist analyst output: {e}")
            sentry_sdk.capture_exception(e)

    async def _persist_fact_checker_output(
        self, session_id: str, result: Dict[str, Any]
    ):
        """Save validated findings & confidence to pipeline_data."""
        try:
            for key in ("validated_findings", "confidence_summary", "bias_analysis"):
                value = result.get(key)
                if value:
                    await ResearchRepository.save_pipeline_data(session_id, key, value)
            logger.info("Persisted fact-checker output to pipeline_data")
        except Exception as e:
            logger.error(f"Failed to persist fact-checker output: {e}")
            sentry_sdk.capture_exception(e)

    @staticmethod
    def _map_source_type(source_type: Optional[str]) -> str:
        mapping = {
            "academic": "academic",
            "news": "news",
            "official": "official",
            "wikipedia": "wikipedia",
            "wiki": "wikipedia",
            "blog": "blog",
        }
        return mapping.get((source_type or "").lower(), "other")

    def _build_final_response(self) -> Dict[str, Any]:
        """Build the final response with all results."""
        
        report_data = self.results.get("report_generator", {}).get("report", {})
        fact_check_data = self.results.get("fact_checker", {})
        analyst_data = self.results.get("analyst", {})
        researcher_data = self.results.get("researcher", {})

        # Use validated findings if available, otherwise fall back through the chain
        findings = fact_check_data.get("validated_findings", [])
        if not findings:
            findings = analyst_data.get("organized_findings", [])
        if not findings:
            findings = analyst_data.get("consolidated_findings", [])
        if not findings:
            findings = researcher_data.get("raw_findings", [])

        return {
            "status": "completed",
            "session_id": self.session_id,
            
            # Core report
            "report": {
                "title": report_data.get("title", ""),
                "summary": report_data.get("summary", ""),
                "markdown_content": report_data.get("markdown_content", ""),
                "html_content": report_data.get("html_content", ""),
                "sections": report_data.get("sections", []),
                "citation_style": report_data.get("citation_style", "APA"),
                "quality_score": report_data.get("quality_score", 0)
            },
            
            # Research data
            "sources": researcher_data.get("sources", []),
            "sources_count": researcher_data.get("sources_count", {}),
            
            # Analysis data
            "findings": findings,
            "patterns": analyst_data.get("patterns", []),
            "key_insights": analyst_data.get("key_insights", []),
            "contradictions": analyst_data.get("contradictions", []),
            
            # Confidence data
            "confidence_summary": fact_check_data.get("confidence_summary", {}),
            "bias_analysis": fact_check_data.get("bias_analysis", {}),
            
            # Metadata
            "metadata": {
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "completed_at": self.completed_at.isoformat() if self.completed_at else None,
                "duration_seconds": (
                    (self.completed_at - self.started_at).total_seconds()
                    if self.completed_at and self.started_at else None
                ),
                "agents_executed": list(self.results.keys()),
                "errors": self.errors if self.errors else None
            }
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get current orchestrator status."""
        
        agent_states = {
            "user_proxy": self.user_proxy.get_state(),
            "researcher": self.researcher.get_state(),
            "analyst": self.analyst.get_state(),
            "fact_checker": self.fact_checker.get_state(),
            "report_generator": self.report_generator.get_state()
        }
        
        # Calculate overall progress
        total_progress = sum(a["progress"] for a in agent_states.values())
        overall_progress = total_progress // 5
        
        return {
            "session_id": self.session_id,
            "phase": self.current_phase.value,
            "is_running": self.is_running,
            "is_cancelled": self.is_cancelled,
            "overall_progress": overall_progress,
            "agents": agent_states,
            "started_at": self.started_at.isoformat() if self.started_at else None
        }
    
    async def cancel(self):
        """Cancel the current research execution."""
        
        logger.info(f"Cancelling research session {self.session_id}")
        self.is_cancelled = True
        
        await self._notify_progress(
            "orchestrator", "cancelled", 0,
            "Research cancelled by user"
        )
