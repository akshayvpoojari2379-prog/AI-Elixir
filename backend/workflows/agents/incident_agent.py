from typing import Dict, Any
from loguru import logger
from integrations.ollama_service import OllamaService
from workflows.state import ServiceDeskState
from workflows.knowledge_engine import KnowledgeEngine

class IncidentAgent:
    def __init__(self):
        self.llm = OllamaService()
        self.kb_engine = KnowledgeEngine()

    async def run(self, state: ServiceDeskState) -> Dict[str, Any]:
        logger.info("Running Incident Workflows Agent...")
        issue_type = state.get("issue_type")
        routing_history = state.get("routing_history", [])
        routing_history.append("IncidentAgent")
        
        skill_details = self.kb_engine.get_skill_details("incident_workflow")
        issue_details = skill_details.get("issues", {}).get(issue_type, {})
        
        sop_steps = issue_details.get("resolution_steps", [])
        display_name = issue_details.get("displayName", "Incident")
        
        prompt = f"""
        You are the specialized Incident Workflows Agent.
        The user is reporting a service disruption: "{display_name}"
        The gathered diagnostic details are: {state.get('clarification_answers')}
        
        SOP Troubleshooting Steps to Execute:
        {chr(10).join([f"{i+1}. {step}" for i, step in enumerate(sop_steps)])}
        
        Generate a conversational troubleshooting guide for the employee. Walk them through the SOP troubleshooting steps to see if they can self-solve the issue immediately, or let them know a ticket is being opened for the network engineering / support desk team. Keep it professional, highly analytical, and clear.
        """
        
        resolution = await self.llm.generate_response(prompt, system_prompt="You are a helpful IT Incident diagnostic and resolution agent.")
        
        return {
            "resolution": resolution,
            "sop_steps": sop_steps,
            "current_sop_step_index": len(sop_steps),
            "resolved": True,
            "ticket_needed": True,
            "routing_history": routing_history
        }
