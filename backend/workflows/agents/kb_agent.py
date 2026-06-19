from typing import Dict, Any
from loguru import logger
from integrations.ollama_service import OllamaService
from workflows.state import ServiceDeskState

class KBAgent:
    def __init__(self):
        self.llm = OllamaService()

    async def run(self, state: ServiceDeskState) -> Dict[str, Any]:
        logger.info("Running KB Agent...")
        query = state.get("query", "")
        routing_history = state.get("routing_history", [])
        routing_history.append("KBAgent")

        prompt = f"""
        The user has asked a question: "{query}"
        
        Provide a helpful and detailed response using standard corporate knowledge guidelines. Keep it professional, informative, and structured.
        """
        response = await self.llm.generate_response(prompt, system_prompt="You are a helpful IT corporate Knowledge Base support assistant.")

        return {
            "resolution": response,
            "resolved": True,
            "ticket_needed": False,
            "routing_history": routing_history
        }
