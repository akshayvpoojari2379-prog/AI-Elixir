from typing import Dict, Any
from loguru import logger
from integrations.ollama_service import OllamaService
from workflows.state import ServiceDeskState
from workflows.knowledge_engine import KnowledgeEngine

class SRAgent:
    def __init__(self):
        self.llm = OllamaService()
        self.kb_engine = KnowledgeEngine()

    async def run(self, state: ServiceDeskState) -> Dict[str, Any]:
        logger.info("Running Service Request (SR) Agent...")
        issue_type = state.get("issue_type")
        routing_history = state.get("routing_history", [])
        routing_history.append("SRAgent")
        
        skill_details = self.kb_engine.get_skill_details("sr_workflow")
        issue_details = skill_details.get("issues", {}).get(issue_type, {})
        
        sop_steps = issue_details.get("resolution_steps", [])
        display_name = issue_details.get("displayName", "Service Request")
        
        prompt = f"""
        You are the specialized Service Request Workflows Agent.
        The user has requested: "{display_name}"
        The gathered details are: {state.get('clarification_answers')}
        
        SOP Operational Steps to Execute:
        {chr(10).join([f"{i+1}. {step}" for i, step in enumerate(sop_steps)])}
        
        Generate a conversational, helpful resolution guide for the employee. Tell them that their service request is being processed according to the SOP steps, explain what will happen next, and reassure them. Keep it professional, encouraging, and clear.
        """
        
        resolution = await self.llm.generate_response(prompt, system_prompt="You are a helpful IT Service Request fulfillment agent.")
        
        return {
            "resolution": resolution,
            "sop_steps": sop_steps,
            "current_sop_step_index": len(sop_steps), # All steps compiled
            "resolved": True,
            "ticket_needed": True, # Logs a ticket in Freshservice
            "routing_history": routing_history
        }
