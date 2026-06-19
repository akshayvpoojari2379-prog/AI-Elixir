from typing import Dict, Any
from loguru import logger
from integrations.ollama_service import OllamaService
from workflows.state import ServiceDeskState
from workflows.knowledge_engine import KnowledgeEngine

class ResolverAgent:
    def __init__(self):
        self.llm = OllamaService()
        self.kb_engine = KnowledgeEngine()

    async def run(self, state: ServiceDeskState) -> Dict[str, Any]:
        logger.info("Running Resolver Workflows Agent...")
        issue_type = state.get("issue_type")
        routing_history = state.get("routing_history", [])
        routing_history.append("ResolverAgent")
        
        skill_details = self.kb_engine.get_skill_details("resolver_workflow")
        issue_details = skill_details.get("issues", {}).get(issue_type, {})
        
        sop_steps = issue_details.get("resolution_steps", [])
        display_name = issue_details.get("displayName", "Resolver Runbook")
        
        prompt = f"""
        You are the specialized Resolver Runbook Workflows Agent.
        The technical resolver requires guidance for: "{display_name}"
        The gathered configuration details are: {state.get('clarification_answers')}
        
        Technical Runbook SOP Steps to Execute:
        {chr(10).join([f"{i+1}. {step}" for i, step in enumerate(sop_steps)])}
        
        Generate a highly technical step-by-step runbook execution guide for the resolver. Explain exactly what scripts to run, what checks to verify, and what commands to execute. Keep it extremely precise, structured, and clear.
        """
        
        resolution = await self.llm.generate_response(prompt, system_prompt="You are a senior systems engineer and technical resolver runbook agent.")
        
        return {
            "resolution": resolution,
            "sop_steps": sop_steps,
            "current_sop_step_index": len(sop_steps),
            "resolved": True,
            "ticket_needed": True,
            "routing_history": routing_history
        }
