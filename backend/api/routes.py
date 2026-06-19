from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from uuid import uuid4
from loguru import logger

from api.schemas import ChatMessageRequest, ChatResponse, FeedbackRequest, TicketCreateRequest, SessionHistoryResponse, MessageHistoryResponse
from database.session import get_db
from database.models import ChatSession, ChatMessage, FeedbackLog
from rag.rag_pipeline import RAGPipeline
from integrations.freshservice_service import FreshserviceService

import easyocr

# Initialize EasyOCR reader globally to avoid reloading models on every request
try:
    logger.info("Initializing global EasyOCR Reader...")
    ocr_reader = easyocr.Reader(['en'], gpu=False)
except Exception as e:
    logger.error(f"Failed to initialize EasyOCR reader: {e}")
    ocr_reader = None

router = APIRouter()

@router.get("/health")
def health_check():
    return {"status": "ok", "service": "AI Service Desk API"}

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatMessageRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        # Session Management
        session_id = request.session_id
        if not session_id:
            db_session = ChatSession()
            db.add(db_session)
            db.commit()
            db.refresh(db_session)
            session_id = str(db_session.id)
        else:
            db_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if not db_session:
                raise HTTPException(status_code=404, detail="Session not found")
        
        # Decode and process uploaded file/image if present
        import os
        extra_content = ""
        if request.file_data:
            try:
                import base64
                file_bytes = base64.b64decode(request.file_data.split(",")[-1])
                name = request.file_name or "uploaded_file"
                ext = os.path.splitext(name)[1].lower()
                
                # Create a temp file path inside the workspace
                temp_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scratch", "uploads")
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, f"{uuid4()}{ext}")
                
                with open(temp_path, "wb") as f:
                    f.write(file_bytes)
                
                logger.info(f"Processing uploaded file {name} ({len(file_bytes)} bytes)")
                
                if ext in ['.png', '.jpg', '.jpeg', '.bmp']:
                    # Image OCR via EasyOCR
                    if ocr_reader is not None:
                        results = ocr_reader.readtext(temp_path)
                    else:
                        reader = easyocr.Reader(['en'], gpu=False)
                        results = reader.readtext(temp_path)
                    ocr_text = " ".join([res[1] for res in results])
                    if ocr_text.strip():
                        extra_content = f" [Attached Image Content: {ocr_text.strip()}]"
                        logger.info(f"Extracted image text: {ocr_text.strip()}")
                elif ext in ['.docx', '.doc']:
                    # Docx conversion via MarkItDown
                    from markitdown import MarkItDown
                    md = MarkItDown()
                    res = md.convert(temp_path)
                    if res.text_content.strip():
                        extra_content = f" [Attached Document Content: {res.text_content.strip()}]"
                        logger.info("Extracted docx content successfully")
                
                # Cleanup temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
            except Exception as fe:
                logger.error(f"Error processing attached file: {str(fe)}")

        # Multi-Agent Workflow Orchestrator (Bypassed for raw Gemma chat testing)
        # from workflows.orchestrator import process_service_desk_query
        # final_message = request.message + extra_content
        # result = await process_service_desk_query(session_id, final_message)
        
        # RAG pipeline + Open Chat Fallback
        from rag.rag_pipeline import RAGPipeline
        from workflows.memory_service import MemoryService
        from integrations.ollama_service import OllamaService
        
        memory_service = MemoryService()
        ollama_service = OllamaService()
        
        final_message = request.message + extra_content
        
        # Save user query to DB history
        memory_service.save_message(session_id=session_id, role="user", content=final_message)
        
        # Load conversation history to provide context
        history = memory_service.load_conversation_history(session_id)
        
        # 1. Try to query the RAG pipeline
        rag_pipeline = RAGPipeline(db)
        rag_result = await rag_pipeline.process_query(final_message, session_history=history[:-1])
        
        # 2. Check if high-confidence matches are found
        if rag_result.get("confidence", 0.0) >= 0.40 and rag_result.get("sources"):
            response_text = rag_result["response"]
            sources = rag_result["sources"]
            routing = ["RAG_Search"]
        else:
            # Fall back to raw model chat for open-ended conversation
            logger.info("No matching knowledge found in RAG. Falling back to open model chat...")
            
            # Construct chat context prompt
            context_prompt = ""
            if len(history) > 1:
                context_prompt = "Conversation history:\n"
                for msg in history[:-1]:
                    context_prompt += f"{msg['role'].capitalize()}: {msg['content']}\n"
            
            response_text = await ollama_service.generate_response(
                prompt=final_message,
                system_prompt=f"{context_prompt}You are a helpful AI assistant. Answer the user's question directly."
            )
            sources = []
            routing = ["OpenChat_ModelDirect"]
            
        # Save assistant response to DB history
        memory_service.save_message(
            session_id=session_id,
            role="assistant",
            content=response_text,
            intent="CHAT",
            confidence=rag_result.get("confidence", 1.0),
            sources=sources
        )
        
        return ChatResponse(
            message=response_text,
            session_id=session_id,
            sources=sources,
            confidence=rag_result.get("confidence", 1.0),
            needs_ticket=False,
            routing_history=routing,
            sop_steps=[],
            intent="CHAT"
        )
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/feedback")
def submit_feedback(request: FeedbackRequest, db: Session = Depends(get_db)):
    feedback = FeedbackLog(
        message_id=request.message_id,
        is_positive=request.is_positive,
        feedback_text=request.feedback_text
    )
    db.add(feedback)
    db.commit()
    return {"status": "success"}

@router.get("/history/{session_id}", response_model=SessionHistoryResponse)
def get_history(session_id: str, db: Session = Depends(get_db)):
    db_session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if not db_session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    
    return SessionHistoryResponse(
        session_id=session_id,
        messages=[
            MessageHistoryResponse(
                id=str(msg.id),
                role=msg.role,
                content=msg.content,
                created_at=msg.created_at,
                sources=msg.sources
            ) for msg in messages
        ]
    )

@router.post("/ticket/create")
async def create_ticket(request: TicketCreateRequest, db: Session = Depends(get_db)):
    fs_service = FreshserviceService()
    try:
        # Assuming description contains necessary data and type
        ticket = await fs_service.create_ticket(
            subject=f"AI Generated {request.type}",
            description=request.description,
            email="employee@elixir.portal", # Should come from authenticated user
            priority=2, # Medium by default
            status=2 # Open
        )
        
        # Link ticket to session
        db_session = db.query(ChatSession).filter(ChatSession.id == request.session_id).first()
        if db_session:
            db_session.ticket_id = str(ticket.get("id"))
            db.commit()
            
        return {"status": "success", "ticket_id": ticket.get("id")}
    except Exception as e:
        logger.error(f"Ticket creation error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create ticket")
