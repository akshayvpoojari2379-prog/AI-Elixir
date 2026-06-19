from typing import List, Dict, Any, Optional, TypedDict

class ServiceDeskState(TypedDict):
    # Core inputs/outputs
    session_id: str
    query: str
    messages: List[Dict[str, str]]
    
    # Intent and routing classification
    intent: Optional[str]          # FAQ_QUERY, TROUBLESHOOTING, INCIDENT_CREATION, SERVICE_REQUEST, ESCALATION, GREETING
    skill: Optional[str]           # sr_workflow, incident_workflow, resolver_workflow, approval_workflow, teams_bot_workflow, faq, kb
    issue_type: Optional[str]      # vendor_mail_missing, expired_links, etc.
    confidence: float
    
    # Clarification track
    clarification_needed: bool
    clarification_questions: List[str] # Questions we need/have to ask
    clarification_answers: Dict[str, str] # Key-value of details gathered
    current_clarification_index: int
    
    # Specialized resolution track
    sop_steps: List[str]          # Standard operating procedure steps for the issue
    current_sop_step_index: int
    resolution: Optional[str]
    resolved: bool
    
    # Ticket automation
    ticket_needed: bool
    ticket_created: bool
    ticket_id: Optional[str]
    ticket_type: Optional[str]    # incident, service_request
    ticket_payload: Optional[Dict[str, Any]]
    ticket_confirmed: Optional[str] # None, "pending", "confirmed", "cancelled"
    
    # Internal routing tracking
    routing_history: List[str]
    next_node: Optional[str]
    errors: List[str]
