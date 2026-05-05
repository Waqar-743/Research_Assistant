"""
MongoDB Document Schemas using Beanie ODM.
Defines all document models for the research assistant.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from beanie import Document, Indexed, Link
from pydantic import Field, EmailStr
import uuid


# ===========================================
# Enums
# ===========================================

class ResearchStatus(str, Enum):
    """Status of a research session."""
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(str, Enum):
    """Status of an individual agent."""
    IDLE = "idle"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceType(str, Enum):
    """Type of information source."""
    NEWS = "news"
    ACADEMIC = "academic"
    OFFICIAL = "official"
    BLOG = "blog"
    WIKIPEDIA = "wikipedia"
    OTHER = "other"


class FindingType(str, Enum):
    """Type of research finding."""
    INSIGHT = "insight"
    STATISTIC = "statistic"
    DEFINITION = "definition"
    CLAIM = "claim"
    FACT = "fact"


class CitationStyle(str, Enum):
    """Citation formatting style."""
    APA = "APA"
    MLA = "MLA"
    CHICAGO = "Chicago"
    HARVARD = "Harvard"


class ResearchMode(str, Enum):
    """Research execution mode."""
    AUTO = "auto"  # Runs automatically without human intervention
    SUPERVISED = "supervised"  # Pauses at checkpoints for approval


# ===========================================
# Embedded Documents (Sub-documents)
# ===========================================

class AgentState(Document):
    """Embedded document for agent state tracking."""
    agent_name: str
    status: AgentStatus = AgentStatus.IDLE
    progress: int = Field(default=0, ge=0, le=100)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    output: Optional[str] = None
    error: Optional[str] = None
    
    class Settings:
        name = "agent_states"


class TokenUsage(Document):
    """Track LLM token usage."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class ReportSection(Document):
    """Section within a report."""
    title: str
    content: str
    order: int
    subsections: Optional[List["ReportSection"]] = None


# ===========================================
# Main Document Models
# ===========================================

class User(Document):
    """User document for authentication and tracking."""
    
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: Indexed(EmailStr, unique=True)
    hashed_password: str
    full_name: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # User preferences
    preferences: Dict[str, Any] = Field(default_factory=lambda: {
        "default_report_format": "markdown",
        "default_citation_style": "APA",
        "research_mode": "auto",
        "notifications_enabled": True
    })
    
    class Settings:
        name = "users"
        indexes = ["email", "user_id"]


class Source(Document):
    """Source document for tracking information sources."""
    
    source_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    research_id: Indexed(str)
    
    url: str
    title: str
    content_preview: Optional[str] = None
    full_content: Optional[str] = None
    
    source_type: SourceType = SourceType.OTHER
    api_source: str  # Which API found this (google, newsapi, arxiv, etc.)
    
    credibility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    bias_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    
    domain: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Settings:
        name = "sources"
        indexes = ["research_id", "source_id", "url"]


class Finding(Document):
    """Research finding document."""
    
    finding_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    research_id: Indexed(str)
    
    title: str
    content: str
    finding_type: FindingType = FindingType.INSIGHT
    
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)
    verified: bool = False
    
    supporting_sources: List[str] = Field(default_factory=list)  # source_ids
    contradicting_sources: List[str] = Field(default_factory=list)
    
    agent_generated_by: str  # Which agent created this finding
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Settings:
        name = "findings"
        indexes = ["research_id", "finding_id"]


class Report(Document):
    """Generated report document."""
    
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    research_id: Indexed(str, unique=True)
    
    title: str
    summary: Optional[str] = None
    
    markdown_content: str
    html_content: Optional[str] = None
    pdf_path: Optional[str] = None
    
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    citation_style: CitationStyle = CitationStyle.APA
    
    quality_score: float = Field(default=0.0, ge=0.0, le=5.0)
    
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = "report_generator"
    
    class Settings:
        name = "reports"
        indexes = ["research_id", "report_id"]


class AgentLog(Document):
    """Detailed agent activity log."""
    
    log_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    research_id: Indexed(str)
    
    agent_name: str
    action: str  # search, analyze, validate, generate
    status: AgentStatus
    
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[int] = None
    
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    tools_used: List[str] = Field(default_factory=list)
    llm_calls: int = 0
    token_usage: Optional[Dict[str, int]] = None
    
    class Settings:
        name = "agent_logs"
        indexes = ["research_id", "agent_name"]


class ResearchSession(Document):
    """Main research session document."""
    
    research_id: Indexed(str, unique=True) = Field(
        default_factory=lambda: f"res_{uuid.uuid4().hex[:12]}"
    )
    user_id: Indexed(str) = Field(default="anonymous")
    
    # Query and configuration
    query: str
    focus_areas: List[str] = Field(default_factory=list)
    source_preferences: List[str] = Field(default_factory=list)
    max_sources: int = Field(default=300, ge=10, le=1000)
    report_format: str = Field(default="markdown")
    citation_style: CitationStyle = CitationStyle.APA
    research_mode: ResearchMode = ResearchMode.AUTO
    
    # Status tracking
    status: ResearchStatus = ResearchStatus.INITIALIZED
    current_stage: Optional[str] = None
    progress: int = Field(default=0, ge=0, le=100)

    # Legacy/current API fields
    current_phase: Optional[str] = None
    agent_statuses: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "user_proxy": {"status": "idle", "progress": 0, "output": None},
            "researcher": {"status": "idle", "progress": 0, "output": None},
            "analyst": {"status": "idle", "progress": 0, "output": None},
            "fact_checker": {"status": "idle", "progress": 0, "output": None},
            "report_generator": {"status": "idle", "progress": 0, "output": None}
        }
    )
    
    # Agent states
    agent_states: Dict[str, Dict[str, Any]] = Field(
        default_factory=lambda: {
            "user_proxy": {"status": "idle", "progress": 0, "output": None},
            "researcher": {"status": "idle", "progress": 0, "output": None},
            "analyst": {"status": "idle", "progress": 0, "output": None},
            "fact_checker": {"status": "idle", "progress": 0, "output": None},
            "report_generator": {"status": "idle", "progress": 0, "output": None}
        }
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Processing metadata
    processing_time_ms: Optional[int] = None
    total_sources: int = 0
    total_findings: int = 0

    # Aggregated counts and summaries
    sources_count: Dict[str, int] = Field(default_factory=dict)
    findings_count: int = 0
    confidence_summary: Dict[str, Any] = Field(default_factory=dict)
    final_report: Optional[Dict[str, Any]] = None
    
    # Quality metrics
    quality_score: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    
    # Inter-agent pipeline data — agents query this by session_id instead
    # of receiving raw payloads.  Keys: "patterns", "key_insights",
    # "contradictions", "organized_findings", "bias_analysis", etc.
    pipeline_data: Dict[str, Any] = Field(default_factory=dict)

    # Error tracking
    error: Optional[str] = None
    error_message: Optional[str] = None
    
    # References to related documents (stored as IDs)
    source_ids: List[str] = Field(default_factory=list)
    finding_ids: List[str] = Field(default_factory=list)
    report_id: Optional[str] = None
    
    class Settings:
        name = "research_sessions"
        indexes = [
            "research_id",
            "user_id",
            "status",
            "created_at"
        ]
    
    def get_processing_time_formatted(self) -> str:
        """Get formatted processing time string."""
        if self.processing_time_ms is None:
            return "N/A"
        
        seconds = self.processing_time_ms / 1000
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
