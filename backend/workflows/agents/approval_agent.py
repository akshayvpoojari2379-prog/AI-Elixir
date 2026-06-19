from typing import Dict, Any
from loguru import logger
from integrations.ollama_service import OllamaService
from workflows.state import ServiceDeskState
from workflows.knowledge_engine import KnowledgeEngine

class ApprovalAgent:
    def __init__(self):
        self.llm = OllamaService()
        self.kb_engine = KnowledgeEngine()

    async def run(self, state: ServiceDeskState) -> Dict[str, Any]:
        logger.info("Running Approval Workflows Agent...")
        issue_type = state.get("issue_type")
        routing_history = state.get("routing_history", [])
        routing_history.append("ApprovalAgent")
        
        skill_details = self.kb_engine.get_skill_details("approval_workflow")
        issue_details = skill_details.get("issues", {}).get(issue_type, {})
        
        sop_steps = issue_details.get("resolution_steps", [])
        display_name = issue_details.get("displayName", "Approval Request")
        
        prompt = f"""
        You are the specialized Approval Workflows Agent.
        The user is querying or initiating: "{display_name}"
        The gathered details are: {state.get('clarification_answers')}
        
        Approval SOP and Authority Matrix Steps:
        {chr(10).join([f"{i+1}. {step}" for i, step in enumerate(sop_steps)])}
        
        Generate a conversational explanation of the approval rules and matrix based on their query. Explain who needs to approve the request, the workflow path it must follow, and how to track the status. Keep it professional, highly structured, and clear.
        """
        
        resolution = await self.llm.generate_response(prompt, system_prompt="You are a helpful IT Finance and Security Approvals assistant.")
        
        return {
            "resolution": resolution,
            "sop_steps": sop_steps,
            "current_sop_step_index": len(sop_steps),
            "resolved": True,
            "ticket_needed": True,
            "routing_history": routing_history
        }
