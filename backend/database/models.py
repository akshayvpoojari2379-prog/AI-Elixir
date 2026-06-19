from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Boolean, Float, JSON
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    sessions = relationship("ChatSession", back_populates="user")
    feedbacks = relationship("FeedbackLog", back_populates="user")


class KBArticle(Base):
    __tablename__ = 'kb_articles'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_file = Column(String(512), nullable=False)
    title = Column(String(512))
    category = Column(String(255), index=True)
    tags = Column(JSON)
    document_type = Column(String(50)) # PDF, DOCX, TXT
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    chunks = relationship("KBChunk", back_populates="article", cascade="all, delete-orphan")


class KBChunk(Base):
    __tablename__ = 'kb_chunks'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    article_id = Column(UUID(as_uuid=True), ForeignKey('kb_articles.id'), nullable=False)
    section_title = Column(String(512))
    content = Column(Text, nullable=False)
    embedding = Column(JSON) # Storing as JSON array for cross-DB compatibility
    chunk_index = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    article = relationship("KBArticle", back_populates="chunks")


class FAQEmbedding(Base):
    __tablename__ = 'faq_embeddings'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(255), index=True)
    embedding = Column(JSON)
    source_file = Column(String(512))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TicketResolutionEmbedding(Base):
    __tablename__ = 'ticket_resolution_embeddings'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(String(100), nullable=False, unique=True, index=True)
    category = Column(String(255), index=True)
    subcategory = Column(String(255))
    description = Column(Text)
    resolution_notes = Column(Text)
    embedding = Column(JSON)
    resolved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatSession(Base):
    __tablename__ = 'chat_sessions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    ticket_id = Column(String(100), nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    last_activity_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(50), default="active") # active, closed, escalated
    
    user = relationship("User", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey('chat_sessions.id'), nullable=False)
    role = Column(String(50), nullable=False) # user, assistant, system
    content = Column(Text, nullable=False)
    intent = Column(String(100))
    confidence_score = Column(Float)
    sources = Column(JSON) # Store citations/sources used
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("ChatSession", back_populates="messages")
    feedbacks = relationship("FeedbackLog", back_populates="message")


class FeedbackLog(Base):
    __tablename__ = 'feedback_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey('chat_messages.id'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    is_positive = Column(Boolean, nullable=False)
    feedback_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    message = relationship("ChatMessage", back_populates="feedbacks")
    user = relationship("User", back_populates="feedbacks")


# ----------------- ENTERPRISE ITSM WORKFLOW OS TABLES -----------------

class EnterpriseDocument(Base):
    __tablename__ = 'enterprise_documents'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_path = Column(String(512), nullable=False, unique=True)
    file_hash = Column(String(64), nullable=False)
    status = Column(String(50), default="pending") # pending, parsed, failed
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExtractedWorkflow(Base):
    __tablename__ = 'extracted_workflows'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey('enterprise_documents.id'), nullable=True)
    workflow_name = Column(String(255), nullable=False)
    domain = Column(String(255))
    steps = Column(JSON) # sequence of steps [ "Step 1", "Step 2" ]
    decision_nodes = Column(JSON) # transitions/conditions
    created_at = Column(DateTime, default=datetime.utcnow)


class OperationalDomain(Base):
    __tablename__ = 'operational_domains'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    categories = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


class SkillRegistry(Base):
    __tablename__ = 'skill_registry'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id = Column(String(255), nullable=False, unique=True, index=True)
    domain_name = Column(String(255), nullable=False)
    description = Column(Text)
    capabilities = Column(JSON) # Capabilities array [ "onboarding", "approvals" ]
    workflow_rules = Column(JSON) # Custom rules or structured JSON
    system_prompt = Column(Text) # Custom prompt for the skillset
    tools = Column(JSON) # MCP tools registered [ "create_incident", ... ]
    escalation_rules = Column(JSON) # Escalation steps
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowRule(Base):
    __tablename__ = 'workflow_rules'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id = Column(String(255), ForeignKey('skill_registry.skill_id'), nullable=False)
    condition_name = Column(String(255), nullable=False)
    condition_logic = Column(JSON) # conditions JSON
    actions = Column(JSON) # actions JSON
    created_at = Column(DateTime, default=datetime.utcnow)


class WorkflowState(Base):
    __tablename__ = 'workflow_states'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey('chat_sessions.id'), nullable=False)
    skill_id = Column(String(255))
    current_step_index = Column(Integer, default=0)
    gathered_data = Column(JSON) # user variables gathered
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RoutingLog(Base):
    __tablename__ = 'routing_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey('chat_sessions.id'), nullable=True)
    query = Column(Text)
    matched_skill = Column(String(255))
    confidence_score = Column(Float)
    routing_history = Column(JSON)
    latency_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)


class DocumentSyncLog(Base):
    __tablename__ = 'document_sync_logs'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    sync_source = Column(String(255))
    documents_detected = Column(Integer)
    documents_processed = Column(Integer)
    status = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
