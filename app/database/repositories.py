"""
Data Access Layer - Repository Pattern for MongoDB Operations.
Provides CRUD operations for all document models.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from beanie import PydanticObjectId

from app.database.schemas import (
    ResearchSession,
    Source,
    Finding,
    Report,
    AgentLog,
    User,
    ResearchStatus,
    AgentStatus
)
from app.utils.logging import logger


# ===========================================
# User Repository
# ===========================================

class UserRepository:
    """Repository for User operations."""
    
    @staticmethod
    async def create(user_data: Dict[str, Any]) -> User:
        """Create a new user."""
        user = User(**user_data)
        await user.insert()
        logger.info(f"Created user: {user.user_id}")
        return user
    
    @staticmethod
    async def get_by_email(email: str) -> Optional[User]:
        """Get user by email."""
        return await User.find_one(User.email == email)
    
    @staticmethod
    async def get_by_id(user_id: str) -> Optional[User]:
        """Get user by user_id."""
        return await User.find_one(User.user_id == user_id)
    
    @staticmethod
    async def update(user_id: str, update_data: Dict[str, Any]) -> Optional[User]:
        """Update user data."""
        user = await User.find_one(User.user_id == user_id)
        if user:
            update_data["updated_at"] = datetime.utcnow()
            await user.update({"$set": update_data})
            return await User.find_one(User.user_id == user_id)
        return None


# ===========================================
# Research Session Repository
# ===========================================

class ResearchRepository:
    """Repository for ResearchSession operations."""
    
    @staticmethod
    async def create(session_data: Dict[str, Any]) -> ResearchSession:
        """Create a new research session."""
        session = ResearchSession(**session_data)
        await session.insert()
        logger.info(f"Created research session: {session.research_id}")
        return session
    
    @staticmethod
    async def get_by_id(research_id: str) -> Optional[ResearchSession]:
        """Get research session by ID."""
        return await ResearchSession.find_one(
            ResearchSession.research_id == research_id
        )

    @staticmethod
    async def get_by_session_id(session_id: str) -> Optional[ResearchSession]:
        """Backward-compatible alias for research session lookup."""
        return await ResearchRepository.get_by_id(session_id)
    
    @staticmethod
    async def get_by_user(
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        status: Optional[ResearchStatus] = None,
        sort_by: str = "created_at"
    ) -> List[ResearchSession]:
        """Get research sessions for a user with pagination."""
        query = ResearchSession.find(ResearchSession.user_id == user_id)
        
        if status:
            query = query.find(ResearchSession.status == status)
        
        # Sorting
        if sort_by == "quality":
            query = query.sort("-quality_score")
        else:
            query = query.sort("-created_at")
        
        return await query.skip(offset).limit(limit).to_list()
    
    @staticmethod
    async def list_sessions(
        skip: int = 0,
        limit: int = 20,
        status_filter: Optional[ResearchStatus] = None,
        search_query: Optional[str] = None
    ) -> List[ResearchSession]:
        """List all research sessions with pagination and filters."""
        query = ResearchSession.find()
        
        if status_filter:
            query = query.find(ResearchSession.status == status_filter)
        
        if search_query:
            query = query.find({"query": {"$regex": search_query, "$options": "i"}})
        
        return await query.sort("-created_at").skip(skip).limit(limit).to_list()

    @staticmethod
    async def count_sessions(
        status_filter: Optional[ResearchStatus] = None,
        search_query: Optional[str] = None
    ) -> int:
        """Count research sessions with filters."""
        query = ResearchSession.find()

        if status_filter:
            query = query.find(ResearchSession.status == status_filter)

        if search_query:
            query = query.find({"query": {"$regex": search_query, "$options": "i"}})

        return await query.count()
    
    @staticmethod
    async def count_by_user(
        user_id: str,
        status: Optional[ResearchStatus] = None
    ) -> int:
        """Count research sessions for a user."""
        query = ResearchSession.find(ResearchSession.user_id == user_id)
        if status:
            query = query.find(ResearchSession.status == status)
        return await query.count()
    
    @staticmethod
    async def update_status(
        research_id: str,
        status: ResearchStatus,
        error: Optional[str] = None
    ) -> Optional[ResearchSession]:
        """Update research session status."""
        session = await ResearchSession.find_one(
            ResearchSession.research_id == research_id
        )
        if session:
            update_data = {"status": status}
            
            if status == ResearchStatus.RUNNING and session.started_at is None:
                update_data["started_at"] = datetime.utcnow()
            
            if status in [ResearchStatus.COMPLETED, ResearchStatus.FAILED]:
                update_data["completed_at"] = datetime.utcnow()
                if session.started_at:
                    delta = datetime.utcnow() - session.started_at
                    update_data["processing_time_ms"] = int(delta.total_seconds() * 1000)
            
            if error:
                update_data["error"] = error
            
            await session.update({"$set": update_data})
            return await ResearchSession.find_one(
                ResearchSession.research_id == research_id
            )
        return None
    
    @staticmethod
    async def update_agent_state(
        research_id: str,
        agent_name: str,
        state: Dict[str, Any]
    ) -> Optional[ResearchSession]:
        """Update specific agent state within a session."""
        session = await ResearchSession.find_one(
            ResearchSession.research_id == research_id
        )
        if session:
            agent_states = session.agent_states
            agent_states[agent_name] = {
                **agent_states.get(agent_name, {}),
                **state
            }
            
            # Calculate overall progress
            total_progress = sum(
                s.get("progress", 0) for s in agent_states.values()
            )
            overall_progress = total_progress // len(agent_states)
            
            await session.update({
                "$set": {
                    "agent_states": agent_states,
                    "progress": overall_progress,
                    "current_stage": agent_name
                }
            })
            return await ResearchSession.find_one(
                ResearchSession.research_id == research_id
            )
        return None
    
    @staticmethod
    async def update_metrics(
        research_id: str,
        total_sources: Optional[int] = None,
        total_findings: Optional[int] = None,
        quality_score: Optional[float] = None,
        confidence: Optional[float] = None
    ) -> Optional[ResearchSession]:
        """Update research metrics."""
        session = await ResearchSession.find_one(
            ResearchSession.research_id == research_id
        )
        if session:
            update_data = {}
            if total_sources is not None:
                update_data["total_sources"] = total_sources
            if total_findings is not None:
                update_data["total_findings"] = total_findings
            if quality_score is not None:
                update_data["quality_score"] = quality_score
            if confidence is not None:
                update_data["confidence"] = confidence
            
            if update_data:
                await session.update({"$set": update_data})
            return await ResearchSession.find_one(
                ResearchSession.research_id == research_id
            )
        return None
    
    @staticmethod
    async def add_source_id(research_id: str, source_id: str):
        """Add a source ID to the session."""
        await ResearchSession.find_one(
            ResearchSession.research_id == research_id
        ).update({"$push": {"source_ids": source_id}})
    
    @staticmethod
    async def add_finding_id(research_id: str, finding_id: str):
        """Add a finding ID to the session."""
        await ResearchSession.find_one(
            ResearchSession.research_id == research_id
        ).update({"$push": {"finding_ids": finding_id}})
    
    @staticmethod
    async def set_report_id(research_id: str, report_id: str):
        """Set the report ID for the session."""
        await ResearchSession.find_one(
            ResearchSession.research_id == research_id
        ).update({"$set": {"report_id": report_id}})

    # ------------------------------------------------------------------
    # Pipeline data helpers — agents save / load intermediate results
    # ------------------------------------------------------------------
    @staticmethod
    async def save_pipeline_data(
        research_id: str,
        key: str,
        value: Any
    ):
        """Store an intermediate result under ``pipeline_data.<key>`` atomically."""
        session = await ResearchSession.find_one(
            ResearchSession.research_id == research_id
        )
        if session:
            # Use dot-notation $set to update a single nested key atomically,
            # avoiding the read-modify-write race condition of the old approach.
            await session.update({"$set": {f"pipeline_data.{key}": value}})

    @staticmethod
    async def get_pipeline_data(
        research_id: str,
        key: Optional[str] = None
    ) -> Any:
        """
        Load pipeline data.  If *key* is given only that slice is
        returned; otherwise the whole ``pipeline_data`` dict is returned.
        """
        session = await ResearchSession.find_one(
            ResearchSession.research_id == research_id
        )
        if session:
            if key:
                return (session.pipeline_data or {}).get(key)
            return session.pipeline_data or {}
        return {} if key is None else None

    @staticmethod
    async def delete(research_id: str) -> bool:
        """Delete a research session and related documents."""
        session = await ResearchSession.find_one(
            ResearchSession.research_id == research_id
        )
        if session:
            # Delete related documents
            await Source.find(Source.research_id == research_id).delete()
            await Finding.find(Finding.research_id == research_id).delete()
            await Report.find(Report.research_id == research_id).delete()
            await AgentLog.find(AgentLog.research_id == research_id).delete()
            
            # Delete session
            await session.delete()
            logger.info(f"Deleted research session: {research_id}")
            return True
        return False


# ===========================================
# Source Repository
# ===========================================

class SourceRepository:
    """Repository for Source operations."""
    
    @staticmethod
    async def create(source_data: Dict[str, Any]) -> Source:
        """Create a new source."""
        source = Source(**source_data)
        await source.insert()
        return source
    
    @staticmethod
    async def create_many(sources: List[Dict[str, Any]]) -> List[Source]:
        """Create multiple sources."""
        source_docs = [Source(**s) for s in sources]
        await Source.insert_many(source_docs)
        return source_docs
    
    @staticmethod
    async def get_by_research(research_id: str) -> List[Source]:
        """Get all sources for a research session."""
        return await Source.find(Source.research_id == research_id).to_list()
    
    @staticmethod
    async def get_by_id(source_id: str) -> Optional[Source]:
        """Get source by ID."""
        return await Source.find_one(Source.source_id == source_id)
    
    @staticmethod
    async def update_credibility(
        source_id: str,
        credibility_score: float,
        bias_score: Optional[float] = None
    ):
        """Update source credibility scores."""
        update_data = {"credibility_score": credibility_score}
        if bias_score is not None:
            update_data["bias_score"] = bias_score
        
        await Source.find_one(
            Source.source_id == source_id
        ).update({"$set": update_data})
    
    @staticmethod
    async def count_by_research(research_id: str) -> int:
        """Count sources for a research session."""
        return await Source.find(Source.research_id == research_id).count()


# ===========================================
# Finding Repository
# ===========================================

class FindingRepository:
    """Repository for Finding operations."""
    
    @staticmethod
    async def create(finding_data: Dict[str, Any]) -> Finding:
        """Create a new finding."""
        finding = Finding(**finding_data)
        await finding.insert()
        return finding
    
    @staticmethod
    async def create_many(findings: List[Dict[str, Any]]) -> List[Finding]:
        """Create multiple findings."""
        finding_docs = [Finding(**f) for f in findings]
        await Finding.insert_many(finding_docs)
        return finding_docs

    @staticmethod
    async def replace_for_research(
        research_id: str,
        findings: List[Dict[str, Any]]
    ) -> List[Finding]:
        """Replace all findings for a research session."""
        await Finding.find(Finding.research_id == research_id).delete()
        if not findings:
            return []

        try:
            finding_docs = [Finding(**f) for f in findings]
            await Finding.insert_many(finding_docs)
            return finding_docs
        except Exception:
            created_docs = []
            for finding in findings:
                created_docs.append(await FindingRepository.create(finding))
            return created_docs
    
    @staticmethod
    async def get_by_research(research_id: str) -> List[Finding]:
        """Get all findings for a research session."""
        return await Finding.find(Finding.research_id == research_id).to_list()
    
    @staticmethod
    async def get_by_id(finding_id: str) -> Optional[Finding]:
        """Get finding by ID."""
        return await Finding.find_one(Finding.finding_id == finding_id)
    
    @staticmethod
    async def mark_verified(finding_id: str, verified: bool, confidence: float):
        """Mark a finding as verified/unverified."""
        await Finding.find_one(
            Finding.finding_id == finding_id
        ).update({
            "$set": {
                "verified": verified,
                "confidence_score": confidence
            }
        })
    
    @staticmethod
    async def count_by_research(research_id: str) -> int:
        """Count findings for a research session."""
        return await Finding.find(Finding.research_id == research_id).count()


# ===========================================
# Report Repository
# ===========================================

class ReportRepository:
    """Repository for Report operations."""
    
    @staticmethod
    async def create(report_data: Dict[str, Any]) -> Report:
        """Create a new report."""
        report = Report(**report_data)
        await report.insert()
        logger.info(f"Created report: {report.report_id}")
        return report
    
    @staticmethod
    async def get_by_research(research_id: str) -> Optional[Report]:
        """Get report for a research session."""
        return await Report.find_one(Report.research_id == research_id)
    
    @staticmethod
    async def get_by_id(report_id: str) -> Optional[Report]:
        """Get report by ID."""
        return await Report.find_one(Report.report_id == report_id)
    
    @staticmethod
    async def update_content(
        report_id: str,
        markdown: Optional[str] = None,
        html: Optional[str] = None,
        pdf_path: Optional[str] = None
    ):
        """Update report content."""
        update_data = {}
        if markdown:
            update_data["markdown_content"] = markdown
        if html:
            update_data["html_content"] = html
        if pdf_path:
            update_data["pdf_path"] = pdf_path
        
        if update_data:
            await Report.find_one(
                Report.report_id == report_id
            ).update({"$set": update_data})


# ===========================================
# Agent Log Repository
# ===========================================

class AgentLogRepository:
    """Repository for AgentLog operations."""
    
    @staticmethod
    async def create(log_data: Dict[str, Any]) -> AgentLog:
        """Create a new agent log entry."""
        log = AgentLog(**log_data)
        await log.insert()
        return log
    
    @staticmethod
    async def get_by_research(research_id: str) -> List[AgentLog]:
        """Get all agent logs for a research session."""
        return await AgentLog.find(
            AgentLog.research_id == research_id
        ).sort(AgentLog.start_time).to_list()
    
    @staticmethod
    async def get_by_agent(
        research_id: str,
        agent_name: str
    ) -> List[AgentLog]:
        """Get logs for a specific agent in a session."""
        return await AgentLog.find(
            AgentLog.research_id == research_id,
            AgentLog.agent_name == agent_name
        ).sort(AgentLog.start_time).to_list()
    
    @staticmethod
    async def complete_log(
        log_id: str,
        status: AgentStatus,
        output_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        token_usage: Optional[Dict[str, int]] = None
    ):
        """Complete an agent log entry."""
        end_time = datetime.utcnow()
        log = await AgentLog.find_one(AgentLog.log_id == log_id)
        
        if log:
            duration_ms = int((end_time - log.start_time).total_seconds() * 1000)
            
            update_data = {
                "status": status,
                "end_time": end_time,
                "duration_ms": duration_ms
            }
            
            if output_data:
                update_data["output_data"] = output_data
            if error:
                update_data["error"] = error
            if token_usage:
                update_data["token_usage"] = token_usage
            
            await log.update({"$set": update_data})
