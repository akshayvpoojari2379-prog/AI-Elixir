import inspect
from typing import Dict, Any, Callable, Optional
from loguru import logger
from integrations.freshservice_service import FreshserviceService
from workflows.knowledge_engine import KnowledgeEngine

class ToolRegistry:
    def __init__(self):
        self._registry: Dict[str, Callable] = {}
        self._metadata: Dict[str, Dict[str, Any]] = {}
        self.kb_engine = KnowledgeEngine()
        self.fs_service = FreshserviceService()

    def register(self, name: str, description: str):
        """Decorator to register a tool with metadata."""
        def decorator(func: Callable):
            self._registry[name] = func
            self._metadata[name] = {
                "name": name,
                "description": description,
                "parameters": inspect.signature(func).parameters
            }
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[Callable]:
        return self._registry.get(name)

    def list_tools(self) -> Dict[str, Any]:
        return self._metadata

# Initialize global registry
registry = ToolRegistry()

# ----------------- TOOL DEFINITIONS -----------------

@registry.register(
    name="get_sr_workflow",
    description="Fetch operational SOPs, access requirements, and provisioning steps for Service Requests (SR)."
)
async def get_sr_workflow(issue_type: str) -> Dict[str, Any]:
    kb = KnowledgeEngine()
    skill_data = kb.get_skill_details("sr_workflow")
    if skill_data and issue_type in skill_data.get("issues", {}):
        return skill_data["issues"][issue_type]
    return {"error": f"Issue type '{issue_type}' not found in Service Request knowledge domain."}



@registry.register(
    name="create_incident",
    description="Submit a new Incident ticket (broken service, errors) to Freshservice."
)
async def create_incident(subject: str, description: str, email: str = "employee@elixir.portal") -> Dict[str, Any]:
    fs = FreshserviceService()
    try:
        ticket = await fs.create_ticket(
            subject=subject,
            description=description,
            email=email,
            priority=2, # Medium
            status=2, # Open
            type="Incident"
        )
        return {"status": "success", "ticket_id": ticket.get("id"), "ticket": ticket}
    except Exception as e:
        logger.error(f"Tool create_incident error: {str(e)}")
        return {"status": "error", "message": str(e)}


@registry.register(
    name="create_service_request",
    description="Submit a new Service Request (onboarding, access, changes) to Freshservice."
)
async def create_service_request(subject: str, description: str, email: str = "employee@elixir.portal") -> Dict[str, Any]:
    fs = FreshserviceService()
    try:
        ticket = await fs.create_ticket(
            subject=subject,
            description=description,
            email=email,
            priority=2, # Medium
            status=2, # Open
            type="Service Request"
        )
        return {"status": "success", "ticket_id": ticket.get("id"), "ticket": ticket}
    except Exception as e:
        logger.error(f"Tool create_service_request error: {str(e)}")
        return {"status": "error", "message": str(e)}


@registry.register(
    name="fetch_ticket_status",
    description="Query Freshservice to check the current status and latest updates of a ticket using its ID."
)
async def fetch_ticket_status(ticket_id: str) -> Dict[str, Any]:
    fs = FreshserviceService()
    try:
        ticket = await fs.get_ticket_status(ticket_id)
        # Map Freshservice numeric status codes to human readable labels
        status_map = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}
        status_val = ticket.get("status", 2)
        status_name = status_map.get(status_val, f"Unknown ({status_val})")
        
        return {
            "status": "success",
            "ticket_id": ticket.get("id"),
            "subject": ticket.get("subject"),
            "status_label": status_name,
            "priority_label": {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}.get(ticket.get("priority", 2), "Medium"),
            "created_at": ticket.get("created_at")
        }
    except Exception as e:
        logger.error(f"Tool fetch_ticket_status error: {str(e)}")
        return {"status": "error", "message": str(e)}


# ----------------- NEW MCP-STYLE SPECIALIZED ITSM TOOLS -----------------

@registry.register(
    name="validate_reporting_manager",
    description="Validate active employee reporting manager mappings against Active Directory/Outlook."
)
async def validate_reporting_manager(employee_email: str) -> Dict[str, Any]:
    logger.info(f"Validating Active Directory reporting manager for: {employee_email}")
    # Simulates an AD lookup
    mock_directory = {
        "employee@elixir.portal": {"manager": "manager@elixir.portal", "status": "active", "department": "IT Support"},
        "newhire@elixir.portal": {"manager": "lead@elixir.portal", "status": "active", "department": "Engineering"}
    }
    
    data = mock_directory.get(employee_email.lower().strip())
    if data:
        return {
            "status": "success",
            "employee": employee_email,
            "manager": data["manager"],
            "manager_status": "valid",
            "department": data["department"],
            "outlook_sync": True
        }
    return {
        "status": "warning",
        "employee": employee_email,
        "manager": "unknown@elixir.portal",
        "manager_status": "missing_mapping",
        "outlook_sync": False,
        "detail": "Manager mapping not found in Outlook Active Directory. Approval triggers may fail."
    }


@registry.register(
    name="get_assignment_group",
    description="Retrieve the target resolver team and escalation routing assignment group for a specific skill domain."
)
async def get_assignment_group(domain: str) -> Dict[str, Any]:
    logger.info(f"Retrieving target assignment group for domain: {domain}")
    routing_map = {
        "service_request_management": "IT Support Desk"
    }
    
    group = routing_map.get(domain.lower().strip(), "IT Support Desk")
    return {
        "domain": domain,
        "target_group": group,
        "sla_resolution_hours": 24,
        "auto_dispatch": True
    }


@registry.register(
    name="fetch_approval_chain",
    description="Fetch corporate multi-stage authorization hierarchies and approver queues based on cost or privilege."
)
async def fetch_approval_chain(ticket_id: str = "FS-999") -> Dict[str, Any]:
    logger.info(f"Fetching multi-stage approval chain for ticket: {ticket_id}")
    # Simulates threshold checks
    return {
        "ticket_id": ticket_id,
        "approval_stages": [
            {"stage": 1, "approver": "manager@elixir.portal", "status": "approved", "timestamp": "2026-05-18T09:12:00Z"},
            {"stage": 2, "approver": "director@elixir.portal", "status": "pending_action", "timestamp": None}
        ],
        "threshold_applied": "Budget > $1000",
        "chain_stuck_at_stage": 2
    }


# ----------------- TOOL EXECUTION ENGINE -----------------

class ToolExecutionEngine:
    def __init__(self):
        self.registry = registry

    async def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Looks up a tool by name and executes it with provided arguments."""
        tool_func = self.registry.get_tool(tool_name)
        if not tool_func:
            logger.error(f"Tool '{tool_name}' not registered in engine.")
            return {"error": f"Tool '{tool_name}' is not registered."}
            
        logger.info(f"Executing tool '{tool_name}' with args {kwargs}")
        try:
            # Handle standard or async function calls
            if inspect.iscoroutinefunction(tool_func):
                result = await tool_func(**kwargs)
            else:
                result = tool_func(**kwargs)
            return result
        except Exception as e:
            logger.error(f"Error executing tool '{tool_name}': {str(e)}")
            return {"error": str(e)}
