from typing import Dict, Any
from loguru import logger
from workflows.state import ServiceDeskState

class SkillRouterAgent:
    def __init__(self):
        pass

    async def run(self, state: ServiceDeskState) -> Dict[str, Any]:
        """
        Skill Routing Agent:
        1. Examines the state (matched skill, intent, confidence).
        2. Determines the exact next Specialized Agent node to invoke in the LangGraph.
        """
        logger.info("Running Skill Routing Agent...")
        skill = state.get("skill")
        intent = state.get("intent", "FAQ_QUERY").upper()
        routing_history = state.get("routing_history", [])
        routing_history.append("SkillRouterAgent")

        # Route to the appropriate specialized workflow agent or default fallback
        target_agent = "incident_agent" # Default ITSM fallback
        
        if skill == "sr_workflow":
            target_agent = "sr_agent"
        elif skill == "incident_workflow":
            target_agent = "incident_agent"
        elif skill == "resolver_workflow":
            target_agent = "resolver_agent"
        elif skill == "approval_workflow":
            target_agent = "approval_agent"
        elif skill == "teams_bot_workflow":
            target_agent = "teams_bot_agent"
        elif intent == "FAQ_QUERY":
            target_agent = "faq_agent"
        elif intent == "GREETING":
            target_agent = "greeting_agent"
        else:
            target_agent = "incident_agent"

        logger.info(f"Routed query to target agent: {target_agent}")

        return {
            "routing_history": routing_history,
            "next_node": target_agent
        }
