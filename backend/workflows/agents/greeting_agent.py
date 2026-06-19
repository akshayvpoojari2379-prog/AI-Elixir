from typing import Dict, Any
from loguru import logger
from integrations.ollama_service import OllamaService
from workflows.state import ServiceDeskState

class GreetingAgent:
    def __init__(self):
        self.llm = OllamaService()

    async def run(self, state: ServiceDeskState) -> Dict[str, Any]:
        logger.info("Running Greeting Agent...")
        query = state.get("query", "")
        routing_history = state.get("routing_history", [])
        routing_history.append("GreetingAgent")

        prompt = f"""
        The user said hello or made a friendly gesture: "{query}"
        
        Respond with a warm, professional greeting and ask how you can help them with their IT support or workflow automation questions today. Keep it short and friendly.
        """
        response = await self.llm.generate_response(prompt, system_prompt="You are a polite, helpful IT service desk virtual assistant.")

        return {
            "resolution": response,
            "resolved": True,
            "ticket_needed": False,
            "routing_history": routing_history
        }
