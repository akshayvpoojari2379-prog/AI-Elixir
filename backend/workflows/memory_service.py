from typing import Dict, Any, List, Optional
from loguru import logger
from sqlalchemy.orm import Session
from database.session import SessionLocal
from database.models import ChatSession, ChatMessage

# Global thread-safe cache for active in-progress LangGraph workflow state
_workflow_states: Dict[str, Dict[str, Any]] = {}

class MemoryService:
    def __init__(self):
        pass

    def get_workflow_state(self, session_id: str) -> Dict[str, Any]:
        """Retrieve cached workflow state variables for an active session."""
        if session_id not in _workflow_states:
            _workflow_states[session_id] = {
                "clarification_answers": {},
                "current_clarification_index": 0,
                "current_sop_step_index": 0,
                "sop_steps": [],
                "routing_history": []
            }
        return _workflow_states[session_id]

    def save_workflow_state(self, session_id: str, state_data: Dict[str, Any]) -> None:
        """Cache state variables for an active session."""
        current_state = self.get_workflow_state(session_id)
        current_state.update(state_data)
        _workflow_states[session_id] = current_state

    def clear_workflow_state(self, session_id: str) -> None:
        """Clear cached workflow states when the interaction finishes or resets."""
        if session_id in _workflow_states:
            del _workflow_states[session_id]

    def load_conversation_history(self, session_id: str) -> List[Dict[str, str]]:
        """Loads and formats conversation history from the PostgreSQL DB."""
        db: Session = SessionLocal()
        try:
            messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
            return [{"role": msg.role, "content": msg.content} for msg in messages]
        except Exception as e:
            logger.error(f"Error loading conversation history for session {session_id}: {str(e)}")
            return []
        finally:
            db.close()

    def save_message(self, session_id: str, role: str, content: str, intent: Optional[str] = None, confidence: Optional[float] = None, sources: Optional[List[Dict[str, Any]]] = None) -> None:
        """Saves a new user or assistant message to the database."""
        db: Session = SessionLocal()
        try:
            from datetime import datetime
            
            # Ensure the session exists in the database
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not session:
                logger.info(f"Creating missing ChatSession for ID {session_id} in DB.")
                session = ChatSession(id=session_id)
                db.add(session)
                db.commit()
                db.refresh(session)

            msg = ChatMessage(
                session_id=session_id,
                role=role,
                content=content,
                intent=intent,
                confidence_score=confidence,
                sources=sources
            )
            db.add(msg)
            
            # Update session last activity
            session.last_activity_at = datetime.utcnow()
                
            db.commit()
        except Exception as e:
            logger.error(f"Error saving message for session {session_id}: {str(e)}")
            db.rollback()
        finally:
            db.close()

    def update_session_ticket(self, session_id: str, ticket_id: str) -> None:
        """Link a created Freshservice ticket to the active chat session."""
        db: Session = SessionLocal()
        try:
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session:
                session.ticket_id = ticket_id
                session.status = "escalated"
                db.commit()
                logger.info(f"Updated session {session_id} with Freshservice ticket ID {ticket_id}")
        except Exception as e:
            logger.error(f"Error updating session ticket: {str(e)}")
            db.rollback()
        finally:
            db.close()
