from typing import Dict, Any, List
from loguru import logger

# Import states and database memory cache
from workflows.state import ServiceDeskState
from workflows.memory_service import MemoryService
from workflows.langgraph_workflows import LangGraphWorkflows

memory_service = MemoryService()
# Initialize the dynamic LangGraph state machine compiled engine
langgraph_app = LangGraphWorkflows()

async def process_service_desk_query(session_id: str, query: str) -> Dict[str, Any]:
    """
    Main orchestration entry point:
    Loads session history/memory, sets up ServiceDeskState, executes the new compiled 
    dynamic LangGraph workflow, and returns a formatted API response.
    """
    logger.info(f"Orchestrating request for session: {session_id} - Query: '{query}'")
    
    # Save the user query to DB history first
    memory_service.save_message(
        session_id=session_id,
        role="user",
        content=query
    )
    
    # 1. Load context from session memory
    history = memory_service.load_conversation_history(session_id)
    cached_state = memory_service.get_workflow_state(session_id)
    
    # 2. Build initial state dict
    initial_state: ServiceDeskState = {
        "session_id": session_id,
        "query": query,
        "messages": history,
        
        "intent": None,
        "skill": cached_state.get("skill"),
        "issue_type": cached_state.get("issue_type"),
        "confidence": cached_state.get("confidence", 0.0),
        
        "clarification_needed": False,
        "clarification_questions": cached_state.get("clarification_questions", []),
        "clarification_answers": cached_state.get("clarification_answers", {}),
        "current_clarification_index": cached_state.get("current_clarification_index", 0),
        
        "sop_steps": cached_state.get("sop_steps", []),
        "current_sop_step_index": cached_state.get("current_sop_step_index", 0),
        "resolution": None,
        "resolved": False,
        
        "ticket_needed": False,
        "ticket_created": False,
        "ticket_id": None,
        "ticket_type": None,
        "ticket_payload": None,
        "ticket_confirmed": cached_state.get("ticket_confirmed"),
        
        "routing_history": cached_state.get("routing_history", []),
        "next_node": cached_state.get("next_node"),
        "errors": []
    }

    # 3. Execute the new compiled Dynamic LangGraph State Machine
    final_output = await langgraph_app.graph.ainvoke(initial_state)

    # 4. Save results and update memory cache
    response_msg = final_output.get("resolution") or "I am analyzing your request. How can I help you today?"
    sources = final_output.get("sources") or []
    intent = final_output.get("intent")
    confidence = final_output.get("confidence", 0.0)
    
    # Check if a ticket was created
    ticket_created = final_output.get("ticket_created", False)
    ticket_id = final_output.get("ticket_id")
    needs_ticket = final_output.get("ticket_needed", False) and not ticket_created

    # Save to history db
    memory_service.save_message(
        session_id=session_id,
        role="assistant",
        content=response_msg,
        intent=intent,
        confidence=confidence,
        sources=sources
    )

    if ticket_created and ticket_id:
        memory_service.update_session_ticket(session_id, ticket_id)

    # Save operational state for future multi-turn dialogue steps
    memory_service.save_workflow_state(session_id, {
        "skill": final_output.get("skill"),
        "issue_type": final_output.get("issue_type"),
        "confidence": confidence,
        "clarification_questions": final_output.get("clarification_questions"),
        "clarification_answers": final_output.get("clarification_answers"),
        "current_clarification_index": final_output.get("current_clarification_index"),
        "sop_steps": final_output.get("sop_steps"),
        "current_sop_step_index": final_output.get("current_sop_step_index"),
        "routing_history": final_output.get("routing_history"),
        "next_node": final_output.get("next_node"),
        "ticket_confirmed": final_output.get("ticket_confirmed")
    })

    return {
        "response": response_msg,
        "sources": sources,
        "confidence": confidence,
        "needs_ticket": needs_ticket,
        "ticket_id": ticket_id,
        "routing_history": final_output.get("routing_history"),
        "sop_steps": final_output.get("sop_steps"),
        "intent": intent
    }
