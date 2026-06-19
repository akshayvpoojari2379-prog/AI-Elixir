from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

class ChatMessageRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    file_data: Optional[str] = None
    file_name: Optional[str] = None
    
class SourceInfo(BaseModel):
    id: int
    title: str
    type: str

class ChatResponse(BaseModel):
    message: str
    session_id: str
    sources: List[SourceInfo] = []
    confidence: float
    needs_ticket: bool
    routing_history: Optional[List[str]] = []
    sop_steps: Optional[List[Any]] = []
    intent: Optional[str] = None
    
class FeedbackRequest(BaseModel):
    message_id: str
    is_positive: bool
    feedback_text: Optional[str] = None

class TicketCreateRequest(BaseModel):
    session_id: str
    description: str
    type: str = "Incident" # or Service Request

class MessageHistoryResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    sources: Optional[List[Dict[str, Any]]] = None

class SessionHistoryResponse(BaseModel):
    session_id: str
    messages: List[MessageHistoryResponse]
