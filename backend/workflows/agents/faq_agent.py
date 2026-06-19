from typing import Dict, Any
from loguru import logger
from integrations.ollama_service import OllamaService
from workflows.state import ServiceDeskState

class FAQAgent:
    def __init__(self):
        self.llm = OllamaService()

    async def run(self, state: ServiceDeskState) -> Dict[str, Any]:
        logger.info("Running FAQ Agent...")
        query = state.get("query", "")
        routing_history = state.get("routing_history", [])
        routing_history.append("FAQAgent")

        prompt = f"""
        The user has asked a general IT question: "{query}"
        
        Provide a helpful, precise, and professional FAQ answer. Keep it structured and brief.
        """
        response = await self.llm.generate_response(prompt, system_prompt="You are a helpful IT FAQ support agent.")

        return {
            "resolution": response,
            "resolved": True,
            "ticket_needed": False,
            "routing_history": routing_history
        }
