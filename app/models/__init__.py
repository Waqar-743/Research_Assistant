"""
Pydantic Models for API Request/Response Validation.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr, validator, AliasChoices
from enum import Enum


# ===========================================
# Enums (matching database schemas)
# ===========================================

class ResearchStatusEnum(str, Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatusEnum(str, Enum):
    IDLE = "idle"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceTypeEnum(str, Enum):
    NEWS = "news"
    ACADEMIC = "academic"
    OFFICIAL = "official"
    BLOG = "blog"
    WIKIPEDIA = "wikipedia"
    OTHER = "other"


class CitationStyleEnum(str, Enum):
    APA = "APA"
    MLA = "MLA"
    CHICAGO = "Chicago"


class ResearchModeEnum(str, Enum):
    AUTO = "auto"
    SUPERVISED = "supervised"


class ReportFormatEnum(str, Enum):
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"


# ===========================================
# Research Request Models
# ===========================================

class ResearchStartRequest(BaseModel):
    """Request model for starting a new research session."""
    
    query: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="The research query/question"
    )
    user_id: Optional[str] = Field(
        default="anonymous",
        description="User ID for tracking"
    )
    focus_areas: Optional[List[str]] = Field(
        default=None,
        max_length=5,
        description="Areas to focus on (e.g., regulatory, technical, ethical)"
    )
    source_preferences: Optional[List[str]] = Field(
        default=None,
        description="Preferred source types (e.g., academic, news, official)"
    )
    max_sources: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Maximum number of sources to collect (quality over quantity)"
    )
    report_format: ReportFormatEnum = Field(
        default=ReportFormatEnum.MARKDOWN,
        description="Output format for the report"
    )
    citation_style: CitationStyleEnum = Field(
        default=CitationStyleEnum.APA,
        description="Citation formatting style"
    )
    research_mode: ResearchModeEnum = Field(
        default=ResearchModeEnum.AUTO,
        description="Execution mode: auto (no intervention) or supervised (checkpoints)"
    )
    
    @validator('query')
    def query_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Query cannot be empty or whitespace')
        return v.strip()
    
    @validator('focus_areas')
    def valid_focus_areas(cls, v):
        if not v:
            return v

        normalized = []
        seen = set()
        for area in v:
            cleaned = area.strip().lower()
            if not cleaned:
                continue
            if len(cleaned) > 50:
                raise ValueError('Focus area entries must be 50 characters or fewer')
            if cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)

        return normalized or None
    
    class Config:
        json_schema_extra = {
            "example": {
                "query": "AI safety frameworks and regulations in 2026",
                "focus_areas": ["regulatory", "technical"],
                "source_preferences": ["academic", "news"],
                "max_sources": 50,
                "report_format": "markdown",
                "citation_style": "APA",
                "research_mode": "auto"
            }
        }


class ResearchFeedbackRequest(BaseModel):
    """Request model for providing feedback during supervised mode."""
    
    approved: bool = Field(..., description="Whether to approve and continue")
    feedback: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional feedback or instructions"
    )
    modifications: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional modifications to research parameters"
    )


# ===========================================
# Agent State Models
# ===========================================

class AgentStateResponse(BaseModel):
    """Response model for individual agent state."""
    
    status: AgentStatusEnum
    progress: int = Field(ge=0, le=100)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    output: Optional[str] = None
    error: Optional[str] = None


class AgentStatesResponse(BaseModel):
    """Response model for all agent states."""
    
    user_proxy: AgentStateResponse
    researcher: AgentStateResponse
    analyst: AgentStateResponse
    fact_checker: AgentStateResponse
    report_generator: AgentStateResponse


# ===========================================
# Source Models
# ===========================================

class SourceResponse(BaseModel):
    """Response model for a source."""
    
    source_id: str
    url: str
    title: str
    content_preview: Optional[str] = None
    source_type: SourceTypeEnum
    api_source: str
    credibility_score: float = Field(ge=0.0, le=1.0)
    domain: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    retrieved_at: datetime
    
    class Config:
        from_attributes = True


class SourcesCountResponse(BaseModel):
    """Response model for source counts by API."""
    
    google: int = 0
    newsapi: int = 0
    arxiv: int = 0
    pubmed: int = 0
    wikipedia: int = 0
    total: int = 0


# ===========================================
# Finding Models
# ===========================================

class FindingResponse(BaseModel):
    """Response model for a finding."""
    
    finding_id: str
    title: str
    content: str
    finding_type: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    verified: bool
    supporting_sources: List[str]
    agent_generated_by: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# ===========================================
# Report Models
# ===========================================

class ReportSectionResponse(BaseModel):
    """Response model for a report section."""
    
    title: str
    content: str
    order: int


class ReportResponse(BaseModel):
    """Response model for a report."""

    report_id: str
    title: str
    summary: Optional[str] = None
    markdown_content: str
    html_content: Optional[str] = None
    sections: List[Dict[str, Any]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    citation_style: CitationStyleEnum = CitationStyleEnum.APA
    quality_score: float = Field(default=0.0, ge=0.0, le=5.0)
    generated_at: datetime

    class Config:
        from_attributes = True


# ===========================================
# Research Response Models
# ===========================================

class ResearchStartResponse(BaseModel):
    """Response model for starting a research session."""
    
    research_id: str
    query: str
    status: ResearchStatusEnum
    created_at: datetime
    websocket_url: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "research_id": "res_abc123def456",
                "query": "AI safety frameworks 2026",
                "status": "initialized",
                "created_at": "2026-01-24T18:39:00Z",
                "websocket_url": "wss://api.example.com/ws/res_abc123def456"
            }
        }


class ResearchStatusResponse(BaseModel):
    """Response model for research status."""
    
    research_id: str
    query: str
    status: ResearchStatusEnum
    current_stage: Optional[str] = None
    progress: int = Field(ge=0, le=100)
    agents: Dict[str, Dict[str, Any]]
    sources_found: SourcesCountResponse
    estimated_completion: Optional[datetime] = None
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "research_id": "res_abc123def456",
                "query": "AI safety frameworks 2026",
                "status": "running",
                "current_stage": "researcher",
                "progress": 35,
                "agents": {
                    "user_proxy": {"status": "completed", "progress": 100},
                    "researcher": {"status": "in_progress", "progress": 65},
                    "analyst": {"status": "queued", "progress": 0},
                    "fact_checker": {"status": "idle", "progress": 0},
                    "report_generator": {"status": "idle", "progress": 0}
                },
                "sources_found": {
                    "google": 45,
                    "newsapi": 23,
                    "arxiv": 12,
                    "pubmed": 8,
                    "wikipedia": 1,
                    "total": 89
                },
                "estimated_completion": "2026-01-24T18:43:30Z",
                "error": None
            }
        }


class ResearchResultsResponse(BaseModel):
    """Response model for completed research results."""
    
    research_id: str
    query: str
    status: ResearchStatusEnum
    created_at: datetime
    completed_at: Optional[datetime] = None
    processing_time: str
    quality_score: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    
    report: Optional[ReportResponse] = None
    findings: List[FindingResponse]
    sources: List[SourceResponse]
    
    metadata: Dict[str, Any]
    
    class Config:
        from_attributes = True


class ResearchHistoryItem(BaseModel):
    """Response model for a history item."""
    
    research_id: str
    query: str
    status: ResearchStatusEnum
    created_at: datetime
    completed_at: Optional[datetime] = None
    quality_score: Optional[float] = None
    sources_count: int
    processing_time: str
    
    class Config:
        from_attributes = True


class ResearchHistoryResponse(BaseModel):
    """Response model for research history."""
    
    total: int
    limit: int
    offset: int
    researches: List[ResearchHistoryItem]


# ===========================================
# User Models
# ===========================================

class UserCreate(BaseModel):
    """Request model for creating a user."""
    
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    """Response model for user data."""
    
    user_id: str
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    preferences: Dict[str, Any]
    
    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    """Response model for authentication token."""
    
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ===========================================
# Generic Response Wrapper
# ===========================================

class APIResponse(BaseModel):
    """Generic API response wrapper."""
    
    status: int
    message: Optional[str] = None
    data: Optional[Any] = None
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": 200,
                "message": "Success",
                "data": {},
                "error": None
            }
        }


# ===========================================
# Document Analysis Enums
# ===========================================

class DocumentStatusEnum(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentTypeEnum(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    MD = "md"


class ResearchTypeEnum(str, Enum):
    QUERY = "query"
    DOCUMENT = "document"
    HYBRID = "hybrid"


class LLMProviderEnum(str, Enum):
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    GPT4 = "gpt4"
    GPT4O = "gpt4o"


class AnalysisDepthEnum(str, Enum):
    QUICK = "quick"
    THOROUGH = "thorough"
    DEEP = "deep"


class ExportFormatEnum(str, Enum):
    PDF = "pdf"
    MARKDOWN = "markdown"
    JSON = "json"
    HTML = "html"


# ===========================================
# Document Request/Response Models
# ===========================================

class DocumentUploadResponse(BaseModel):
    """Response model for document upload."""
    
    document_id: str
    filename: str
    file_size: int
    status: DocumentStatusEnum
    uploaded_at: datetime
    
    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    """Response model for a document."""
    
    document_id: str
    filename: str
    original_filename: str
    file_size: int
    document_type: DocumentTypeEnum
    status: DocumentStatusEnum
    processing_progress: int = 0
    
    # Content info
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    
    # Analysis results
    summary: Optional[str] = None
    topics: List[str] = []
    key_findings: List[str] = []
    
    # Timestamps
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    """Response model for document list."""
    
    total: int
    limit: int
    offset: int
    documents: List[DocumentResponse]


class CitationResponse(BaseModel):
    """Response model for a citation."""
    
    citation_id: str
    raw_text: str
    formatted_apa: Optional[str] = None
    formatted_mla: Optional[str] = None
    formatted_chicago: Optional[str] = None
    formatted_harvard: Optional[str] = None
    authors: List[str] = []
    title: Optional[str] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    
    class Config:
        from_attributes = True


class ComparisonRequest(BaseModel):
    """Request model for document comparison."""
    
    document_ids: List[str] = Field(
        ...,
        min_length=2,
        max_length=5,
        description="IDs of documents to compare"
    )


class ComparisonResponse(BaseModel):
    """Response model for document comparison."""
    
    comparison_id: str
    document_ids: List[str]
    similarities: List[Dict[str, Any]]
    differences: List[Dict[str, Any]]
    recommendation: Optional[str] = None
    overall_analysis: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class SummarizeRequest(BaseModel):
    """Request model for document summarization."""
    
    length: str = Field(
        default="medium",
        pattern="^(short|medium|long)$",
        description="Summary length: short, medium, or long"
    )


# ===========================================
# Hybrid Research Models
# ===========================================

class HybridResearchRequest(BaseModel):
    """Request model for starting hybrid research."""
    
    # Document analysis
    document_ids: List[str] = Field(
        default=[],
        max_length=10,
        description="IDs of documents to analyze"
    )
    
    # Web search
    search_query: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional web search query"
    )
    
    # Research mode
    mode: ResearchTypeEnum = Field(
        default=ResearchTypeEnum.HYBRID,
        description="Research type: query, document, or hybrid"
    )
    
    # Agent configuration
    agents_enabled: Optional[Dict[str, bool]] = Field(
        default=None,
        description="Which agents to enable"
    )
    
    # Analysis settings
    analysis_depth: AnalysisDepthEnum = Field(
        default=AnalysisDepthEnum.THOROUGH,
        description="Analysis depth: quick, thorough, or deep"
    )
    
    # Inherited from ResearchStartRequest
    focus_areas: Optional[List[str]] = None
    max_sources: int = Field(default=100, ge=10, le=500)
    report_format: ReportFormatEnum = Field(default=ReportFormatEnum.MARKDOWN)
    citation_style: CitationStyleEnum = Field(default=CitationStyleEnum.APA)
    research_mode: ResearchModeEnum = Field(default=ResearchModeEnum.AUTO)
    
    @validator('mode')
    def validate_mode_with_inputs(cls, v, values):
        doc_ids = values.get('document_ids', [])
        query = values.get('search_query')
        
        if v == ResearchTypeEnum.DOCUMENT and not doc_ids:
            raise ValueError('Document mode requires at least one document_id')
        if v == ResearchTypeEnum.QUERY and not query:
            raise ValueError('Query mode requires a search_query')
        
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_ids": ["doc_abc123", "doc_def456"],
                "search_query": "AI safety regulations 2026",
                "mode": "hybrid",
                "analysis_depth": "thorough",
                "agents_enabled": {
                    "researcher": True,
                    "analyst": True,
                    "fact_checker": True,
                    "report_generator": True,
                    "document_analyzer": True
                }
            }
        }


# ===========================================
# Chat/Conversation Models
# ===========================================

class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message."""
    
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Message content",
        validation_alias=AliasChoices("message", "content")
    )
    document_ids: Optional[List[str]] = Field(
        default=None,
        description="Document IDs to use as context",
        validation_alias=AliasChoices("document_ids", "document_context_ids")
    )


class ChatMessageResponse(BaseModel):
    """Response model for a chat message."""
    
    message_id: str
    role: str  # "user" or "assistant"
    content: str
    agent_name: Optional[str] = None
    sources: List[str] = []
    document_refs: List[str] = []
    timestamp: datetime
    
    class Config:
        from_attributes = True


class ConversationHistoryResponse(BaseModel):
    """Response model for conversation history."""
    
    research_id: str
    messages: List[ChatMessageResponse]
    message_count: int
    created_at: datetime
    last_message_at: Optional[datetime] = None


# ===========================================
# Export Models
# ===========================================

class ExportRequest(BaseModel):
    """Request model for exporting research."""
    
    format: ExportFormatEnum = Field(
        default=ExportFormatEnum.PDF,
        description="Export format"
    )
    include_summaries: bool = Field(default=True)
    include_citations: bool = Field(default=True)
    include_conversation: bool = Field(default=True)
    include_sources: bool = Field(default=True)
    citation_style: CitationStyleEnum = Field(default=CitationStyleEnum.APA)


class ExportResponse(BaseModel):
    """Response model for export."""
    
    download_url: Optional[str] = None
    filename: str
    format: ExportFormatEnum
    file_size: Optional[int] = None
    generated_at: datetime


# ===========================================
# User Settings Models
# ===========================================

class UserSettingsRequest(BaseModel):
    """Request model for updating user settings."""
    
    llm_provider: Optional[LLMProviderEnum] = None
    custom_api_key: Optional[str] = Field(
        default=None,
        description="Custom OpenRouter API key (will be encrypted)"
    )
    agents_enabled: Optional[Dict[str, bool]] = None
    auto_summarize: Optional[bool] = None
    auto_extract_citations: Optional[bool] = None
    max_batch_size: Optional[int] = Field(default=None, ge=1, le=20)
    default_research_mode: Optional[str] = None
    default_analysis_depth: Optional[str] = None
    default_citation_style: Optional[str] = None
    default_report_format: Optional[str] = None
    notifications_enabled: Optional[bool] = None


class UserSettingsResponse(BaseModel):
    """Response model for user settings."""
    
    settings_id: str
    user_id: str
    theme: str = "system"
    default_citation_style: str = "APA"
    auto_save: bool = True
    notifications_enabled: bool = True
    llm_preferences: Dict[str, Any] = {}
    research_preferences: Dict[str, Any] = {}
    export_preferences: Dict[str, Any] = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Legacy fields for backwards compatibility
    llm_provider: Optional[LLMProviderEnum] = None
    has_custom_api_key: bool = False
    agents_enabled: Optional[Dict[str, bool]] = None
    auto_summarize: bool = True
    auto_extract_citations: bool = True
    max_batch_size: int = 10
    default_research_mode: str = "auto"
    default_analysis_depth: str = "thorough"
    default_report_format: str = "markdown"
    
    class Config:
        from_attributes = True
