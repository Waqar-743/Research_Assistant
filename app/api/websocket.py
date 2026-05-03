"""
WebSocket Handler
Real-time bidirectional communication for research progress updates.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, Optional, Any
from datetime import datetime
import json
import asyncio

from app.utils.logging import logger


router = APIRouter()


class ConnectionManager:
    """
    Manages WebSocket connections for research sessions.
    """
    
    def __init__(self):
        # Map of session_id -> list of WebSocket connections
        self.active_connections: Dict[str, list[WebSocket]] = {}
        # Map of session_id -> asyncio.Queue for messages
        self.message_queues: Dict[str, asyncio.Queue] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
            self.message_queues[session_id] = asyncio.Queue()
        
        self.active_connections[session_id].append(websocket)
        logger.info(f"WebSocket connected for session {session_id}")
        
        # Send connection confirmation
        await self.send_personal_message(
            websocket,
            {
                "type": "connection_established",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def disconnect(self, websocket: WebSocket, session_id: str):
        """Remove a WebSocket connection."""
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            
            # Clean up if no more connections
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
                if session_id in self.message_queues:
                    del self.message_queues[session_id]
        
        logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send message to a specific WebSocket."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send WebSocket message: {e}")
    
    async def broadcast_to_session(self, session_id: str, message: dict):
        """Broadcast message to all connections for a session."""
        if session_id in self.active_connections:
            # Add timestamp if not present
            if "timestamp" not in message:
                message["timestamp"] = datetime.utcnow().isoformat()
            
            disconnected = []
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to broadcast to connection: {e}")
                    disconnected.append(connection)
            
            # Remove disconnected clients
            for conn in disconnected:
                self.active_connections[session_id].remove(conn)
    
    def get_connection_count(self, session_id: str) -> int:
        """Get number of active connections for a session."""
        return len(self.active_connections.get(session_id, []))
    
    def has_connections(self, session_id: str) -> bool:
        """Check if session has any active connections."""
        return session_id in self.active_connections and len(self.active_connections[session_id]) > 0


# Global connection manager instance
manager = ConnectionManager()


def _format_key_findings(value) -> str:
    if isinstance(value, list):
        return "\n".join(
            f"- {item}" for item in value if isinstance(item, str) and item.strip()
        )
    if isinstance(value, str):
        return value.strip()
    return ""


def _build_report_context_text(query: str, report: dict) -> str:
    if not report:
        return f"Research Query: {query}" if query else ""

    summary = (report.get("summary") or report.get("executive_summary") or "").strip()
    key_findings = _format_key_findings(report.get("key_findings"))
    markdown_content = str(report.get("markdown_content") or "").strip()
    sections = report.get("sections") or []

    if not key_findings and sections:
        key_findings = "\n".join(
            f"- {section.get('title', 'Section')}"
            for section in sections[:5]
            if isinstance(section, dict) and section.get("title")
        )

    parts = []
    if query:
        parts.append(f"Research Query: {query}")
    if summary:
        parts.append(f"Executive Summary: {summary}")
    if key_findings:
        parts.append(f"Key Findings:\n{key_findings}")
    if markdown_content:
        parts.append(f"Report Content:\n{markdown_content[:12000]}")

    return "\n\n".join(parts)


async def send_agent_update(
    session_id: str,
    agent_name: str,
    status: str,
    progress: int,
    output: Optional[str] = None,
    error: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None
):
    """
    Send agent status update via WebSocket.
    
    This is the callback function used by agents to send real-time updates.
    
    Message format (matches frontend expectation):
    {
        "type": "agent_status_update",
        "agent": "researcher",
        "status": "in_progress",
        "progress": 65,
        "timestamp": "2024-01-15T10:30:00.000Z",
        "data": {...}
    }
    """
    message = {
        "type": "agent_status_update",
        "agent": agent_name,
        "status": status,
        "progress": progress,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if output:
        message["output"] = output
    if error:
        message["error"] = error
    if data:
        message["data"] = data
    
    await manager.broadcast_to_session(session_id, message)


async def send_phase_update(
    session_id: str,
    phase: str,
    status: str,
    message_text: Optional[str] = None
):
    """Send workflow phase update."""
    message = {
        "type": "phase_update",
        "phase": phase,
        "status": status,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if message_text:
        message["message"] = message_text
    
    await manager.broadcast_to_session(session_id, message)


async def send_research_complete(
    session_id: str,
    results: Dict[str, Any]
):
    """Send research completion notification."""
    message = {
        "type": "research_complete",
        "session_id": session_id,
        "status": "completed",
        "timestamp": datetime.utcnow().isoformat(),
        "results": {
            "report_title": results.get("report", {}).get("title", ""),
            "sources_count": results.get("sources_count", {}),
            "findings_count": len(results.get("findings", [])),
            "confidence_level": results.get("confidence_summary", {}).get("confidence_level", "medium"),
            "quality_score": results.get("report", {}).get("quality_score", 0)
        }
    }
    
    await manager.broadcast_to_session(session_id, message)


async def send_research_error(
    session_id: str,
    error: str,
    phase: Optional[str] = None
):
    """Send research error notification."""
    message = {
        "type": "research_error",
        "session_id": session_id,
        "error": error,
        "phase": phase,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    await manager.broadcast_to_session(session_id, message)


async def send_approval_request(
    session_id: str,
    checkpoint: str,
    data: Dict[str, Any]
):
    """Send approval request for supervised mode."""
    message = {
        "type": "approval_request",
        "session_id": session_id,
        "checkpoint": checkpoint,
        "data": data,
        "timestamp": datetime.utcnow().isoformat(),
        "awaiting_response": True
    }
    
    await manager.broadcast_to_session(session_id, message)


@router.websocket("/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for research session updates.
    
    Clients connect here to receive real-time updates about research progress.
    Also handles bidirectional communication for supervised mode feedback.
    A server-initiated ping is sent every 15 s to keep the connection alive
    through proxies and load balancers.
    """
    await manager.connect(websocket, session_id)

    async def heartbeat_sender():
        """Send a ping frame every 15 s to prevent idle-timeout disconnects."""
        try:
            while True:
                await asyncio.sleep(15)
                try:
                    await websocket.send_json({
                        "type": "ping",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception:
                    break
        except asyncio.CancelledError:
            pass

    async def message_receiver():
        """Receive and handle client messages."""
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                await handle_client_message(session_id, message)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")
                await manager.send_personal_message(websocket, {
                    "type": "error",
                    "message": "Invalid JSON format"
                })

    heartbeat_task = asyncio.create_task(heartbeat_sender())
    try:
        await message_receiver()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        heartbeat_task.cancel()
        manager.disconnect(websocket, session_id)


async def handle_client_message(session_id: str, message: dict):
    """Handle messages received from WebSocket clients."""
    
    message_type = message.get("type")
    
    if message_type == "ping":
        # Heartbeat response
        await manager.broadcast_to_session(session_id, {
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    elif message_type == "approval_response":
        # Handle user approval/rejection in supervised mode
        from app.services.research_service import get_research_service
        
        approved = message.get("approved", False)
        feedback = message.get("feedback", "")
        modifications = message.get("modifications", {})
        
        service = get_research_service()
        await service.process_feedback(
            session_id=session_id,
            approved=approved,
            feedback=feedback,
            modifications=modifications
        )
    
    elif message_type == "cancel":
        # Handle cancel request
        from app.services.research_service import get_research_service
        
        service = get_research_service()
        await service.cancel_research(session_id)
    
    elif message_type == "status_request":
        # Send current status
        from app.database.repositories import ResearchRepository
        
        session = await ResearchRepository.get_by_session_id(session_id)
        if session:
            await manager.broadcast_to_session(session_id, {
                "type": "status_response",
                "session_id": session_id,
                "status": session.status.value,
                "progress": session.progress or 0,
                "phase": session.current_phase or session.current_stage,
                "agent_statuses": session.agent_statuses or {},
                "timestamp": datetime.utcnow().isoformat()
            })
    
    elif message_type == "chat_message":
        # Handle real-time chat message
        await handle_chat_message(session_id, message)
    
    else:
        logger.warning(f"Unknown message type: {message_type}")


async def handle_chat_message(session_id: str, message: dict):
    """
    Handle real-time chat messages via WebSocket.
    
    Message format:
    {
        "type": "chat_message",
        "content": "What are the key findings?",
        "user_id": "anonymous",
        "document_ids": ["doc1", "doc2"]  // optional
    }
    """
    from app.database.document_repository import DocumentRepository, ConversationRepository
    from app.database.document_schemas import ConversationMessage, ConversationRole
    from app.database.repositories import ResearchRepository
    from app.agents.document_analyzer import DocumentAnalyzer
    
    user_content = message.get("content", "")
    user_id = message.get("user_id", "anonymous")
    document_ids = message.get("document_ids", [])
    
    if not user_content:
        await manager.broadcast_to_session(session_id, {
            "type": "chat_error",
            "error": "Empty message content",
            "timestamp": datetime.utcnow().isoformat()
        })
        return
    
    # Send acknowledgment
    await manager.broadcast_to_session(session_id, {
        "type": "chat_message_received",
        "content": user_content,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    try:
        # Get or create conversation
        conversation = await ConversationRepository.get_by_session(session_id)
        
        if not conversation:
            # Fetch session context
            session = await ResearchRepository.get_by_session_id(session_id)
            
            if not session:
                await manager.broadcast_to_session(session_id, {
                    "type": "chat_error",
                    "error": "Research session not found",
                    "timestamp": datetime.utcnow().isoformat()
                })
                return
            
            context = {
                "query": session.query,
                "report": session.final_report or {},
                "sources_count": session.sources_count or {}
            }
            
            conversation = await ConversationRepository.create({
                "session_id": session_id,
                "user_id": user_id,
                "document_ids": document_ids,
                "context": context,
                "messages": []
            })
        
        # Add user message
        user_message = ConversationMessage(
            role=ConversationRole.USER,
            content=user_content,
            timestamp=datetime.utcnow()
        )
        await ConversationRepository.add_message(conversation.conversation_id, user_message)
        
        # Build context for the question
        context_text = ""
        if conversation.context:
            context_text = _build_report_context_text(
                conversation.context.get("query", ""),
                conversation.context.get("report") or {}
            )
        
        # Add document context
        if document_ids:
            for doc_id in document_ids:
                doc = await DocumentRepository.get_by_id(doc_id)
                if doc:
                    context_text += f"\n--- Document: {doc.filename} ---\n"
                    context_text += f"Summary: {doc.summary or 'No summary'}\n"
                    if doc.extracted_text:
                        context_text += f"Content: {doc.extracted_text[:5000]}...\n"
        
        # Send typing indicator
        await manager.broadcast_to_session(session_id, {
            "type": "chat_typing",
            "is_typing": True,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Get response from analyzer
        analyzer = DocumentAnalyzer()
        response = await analyzer.answer_question(
            question=user_content,
            document_context=context_text,
            chat_history=[
                {"role": m.role.value, "content": m.content}
                for m in (conversation.messages or [])[-10:]
            ]
        )
        
        assistant_content = response.get("answer", "I couldn't generate a response.")
        
        # Create assistant message
        assistant_message = ConversationMessage(
            role=ConversationRole.ASSISTANT,
            content=assistant_content,
            timestamp=datetime.utcnow(),
            metadata={
                "confidence": response.get("confidence"),
                "sources_used": response.get("sources_used", [])
            }
        )
        await ConversationRepository.add_message(conversation.conversation_id, assistant_message)
        
        # Send response
        await manager.broadcast_to_session(session_id, {
            "type": "chat_response",
            "message_id": assistant_message.message_id,
            "role": "assistant",
            "content": assistant_content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "confidence": response.get("confidence"),
                "sources_used": response.get("sources_used", [])
            }
        })
        
        # Stop typing indicator
        await manager.broadcast_to_session(session_id, {
            "type": "chat_typing",
            "is_typing": False,
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Chat message handling failed: {e}")
        await manager.broadcast_to_session(session_id, {
            "type": "chat_error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        })


async def send_chat_message(
    session_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None
):
    """Send a chat message to all session clients."""
    message = {
        "type": "chat_response",
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if metadata:
        message["metadata"] = metadata
    
    await manager.broadcast_to_session(session_id, message)


def get_manager() -> ConnectionManager:
    """Get the global connection manager."""
    return manager
