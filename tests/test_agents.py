"""
Test Suite for Multi-Agent Research Assistant
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

# Mark all tests as async
pytestmark = pytest.mark.asyncio


class TestAgentBase:
    """Test base agent functionality."""
    
    async def test_agent_initialization(self):
        """Test agent can be initialized."""
        from app.agents.base_agent import BaseAgent, AgentStatus
        
        # BaseAgent is abstract, so we need to create a concrete implementation
        class TestAgent(BaseAgent):
            async def execute(self, context):
                return {"status": "completed"}
        
        agent = TestAgent(
            name="Test Agent",
            role="Testing",
            system_prompt="You are a test agent.",
            model="test-model"
        )
        
        assert agent.name == "Test Agent"
        assert agent.status == AgentStatus.IDLE
        assert agent.progress == 0
    
    async def test_agent_state(self):
        """Test agent state retrieval."""
        from app.agents.base_agent import BaseAgent, AgentStatus
        
        class TestAgent(BaseAgent):
            async def execute(self, context):
                return {"status": "completed"}
        
        agent = TestAgent(
            name="Test",
            role="Test",
            system_prompt="Test",
            model="test"
        )
        
        state = agent.get_state()
        
        assert "name" in state
        assert "status" in state
        assert "progress" in state
        assert state["status"] == "idle"


class TestResearcher:
    """Test Researcher agent."""
    
    async def test_researcher_initialization(self):
        """Test researcher agent initialization."""
        from app.agents.researcher import ResearcherAgent
        
        researcher = ResearcherAgent()
        
        assert researcher.name == "Researcher"
        assert researcher.search_tools is not None


class TestAnalyst:
    """Test Analyst agent."""
    
    async def test_analyst_initialization(self):
        """Test analyst agent initialization."""
        from app.agents.analyst import AnalystAgent
        
        analyst = AnalystAgent()
        
        assert analyst.name == "Analyst"


class TestFactChecker:
    """Test Fact-Checker agent."""
    
    async def test_fact_checker_initialization(self):
        """Test fact checker agent initialization."""
        from app.agents.fact_checker import FactCheckerAgent
        
        fact_checker = FactCheckerAgent()
        
        assert fact_checker.name == "Fact-Checker"
        assert fact_checker.validation_tools is not None


class TestReportGenerator:
    """Test Report Generator agent."""
    
    async def test_report_generator_initialization(self):
        """Test report generator agent initialization."""
        from app.agents.report_generator import ReportGeneratorAgent
        
        generator = ReportGeneratorAgent()
        
        assert generator.name == "Report Generator"
        assert generator.formatting_tools is not None


class TestOrchestrator:
    """Test Agent Orchestrator."""
    
    async def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        from app.agents.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        
        assert orchestrator.user_proxy is not None
        assert orchestrator.researcher is not None
        assert orchestrator.analyst is not None
        assert orchestrator.fact_checker is not None
        assert orchestrator.report_generator is not None
    
    async def test_orchestrator_status(self):
        """Test orchestrator status reporting."""
        from app.agents.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        status = orchestrator.get_status()
        
        assert "phase" in status
        assert "agents" in status
        assert "overall_progress" in status


class TestSearchTools:
    """Test search tools."""
    
    async def test_search_tools_initialization(self):
        """Test search tools initialization."""
        from app.tools.search_tools import SearchTools
        
        tools = SearchTools()
        
        assert tools is not None
    
    @patch('aiohttp.ClientSession')
    async def test_wikipedia_search(self, mock_session):
        """Test Wikipedia search."""
        from app.tools.search_tools import SearchTools
        
        tools = SearchTools()
        
        # Mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "query": {
                "search": [
                    {"title": "Test", "snippet": "Test snippet"}
                ]
            }
        })
        
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
        
        # Note: Actual test would require proper mocking of aiohttp


class TestValidationTools:
    """Test validation tools."""
    
    async def test_validation_tools_initialization(self):
        """Test validation tools initialization."""
        from app.tools.validation_tools import ValidationTools
        
        tools = ValidationTools()
        
        assert tools is not None


class TestFormattingTools:
    """Test formatting tools."""
    
    async def test_formatting_tools_initialization(self):
        """Test formatting tools initialization."""
        from app.tools.formatting_tools import FormattingTools
        
        tools = FormattingTools()
        
        assert tools is not None
    
    async def test_citation_formatting_apa(self):
        """Test APA citation formatting."""
        from app.tools.formatting_tools import FormattingTools
        
        tools = FormattingTools()
        
        sources = [
            {
                "title": "Test Article",
                "url": "https://example.com",
                "author": "John Doe",
                "published_date": "2024-01-15"
            }
        ]
        
        citations = await tools.format_citations(sources, "APA")
        
        assert len(citations) > 0


class TestModels:
    """Test Pydantic models."""
    
    def test_research_start_request(self):
        """Test ResearchStartRequest model."""
        from app.models import ResearchStartRequest
        
        request = ResearchStartRequest(
            query="Test query",
            focus_areas=["technical", "ethical"],
            research_mode="auto"
        )
        
        assert request.query == "Test query"
        assert len(request.focus_areas) == 2
        assert request.research_mode == "auto"
    
    def test_api_response(self):
        """Test APIResponse model."""
        from app.models import APIResponse
        
        response = APIResponse(
            status=200,
            message="Test message",
            data={"key": "value"}
        )
        
        assert response.status == 200
        assert response.message == "Test message"


class TestDatabaseSchemas:
    """Test database schemas."""
    
    def test_research_session_creation(self):
        """Test ResearchSession schema."""
        from app.database.schemas import ResearchSession, ResearchStatus
        
        # model_construct bypasses __init__ and validation, avoiding Beanie's collection check
        session = ResearchSession.model_construct(
            research_id="res-123",
            user_id="user-456",
            query="Test query",
            status=ResearchStatus.INITIALIZED
        )
        
        assert session.research_id == "res-123"
        assert session.status == ResearchStatus.INITIALIZED


class TestWebSocket:
    """Test WebSocket functionality."""
    
    async def test_connection_manager_initialization(self):
        """Test connection manager."""
        from app.api.websocket import ConnectionManager
        
        manager = ConnectionManager()
        
        assert manager.active_connections == {}
    
    async def test_connection_count(self):
        """Test connection counting."""
        from app.api.websocket import ConnectionManager
        
        manager = ConnectionManager()
        
        count = manager.get_connection_count("test-session")
        
        assert count == 0


class TestResearchApiHelpers:
    """Test backend helper fallbacks for report/chat/results."""

    def test_pipeline_findings_are_normalized(self):
        from app.api.v1.research import _build_pipeline_findings
        from app.database.schemas import ResearchSession

        session = ResearchSession.model_construct(
            research_id="res-123",
            user_id="user-456",
            query="Test query",
            created_at=datetime.utcnow(),
            pipeline_data={
                "validated_findings": [
                    {
                        "id": "finding_1",
                        "title": "Validated finding",
                        "content": "A validated finding with evidence.",
                        "finding_type": "fact",
                        "confidence": "high",
                        "verified": True,
                        "resolved_sources": [{"url": "https://example.com/source"}],
                    }
                ]
            }
        )

        findings = _build_pipeline_findings(session)

        assert len(findings) == 1
        assert findings[0]["finding_id"] == "finding_1"
        assert findings[0]["verified"] is True
        assert findings[0]["supporting_sources"] == ["https://example.com/source"]
        assert findings[0]["confidence_score"] > 0.8

    def test_report_context_supports_current_report_shape(self):
        from app.api.v1.research import _build_report_context_text

        context = _build_report_context_text(
            "AI safety",
            {
                "summary": "Summary text",
                "markdown_content": "## Evidence\nSome details",
                "sections": [{"title": "Evidence", "content": "Some details"}],
            }
        )

        assert "Research Query: AI safety" in context
        assert "Executive Summary: Summary text" in context
        assert "Key Findings:\n- Evidence" in context
        assert "Report Content:\n## Evidence" in context


# Configuration for pytest
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )
