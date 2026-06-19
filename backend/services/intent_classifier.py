from loguru import logger
from integrations.ollama_service import OllamaService
from prompts.rag_prompts import INTENT_CLASSIFICATION_PROMPT

class IntentClassifier:
    def __init__(self):
        self.llm_service = OllamaService()
        self.valid_intents = [
            "FAQ_QUERY",
            "TROUBLESHOOTING",
            "INCIDENT_CREATION",
            "SERVICE_REQUEST",
            "ESCALATION",
            "GREETING"
        ]

    async def classify_intent(self, user_input: str) -> str:
        """Classifies the intent of the user input using fast rule-based matching."""
        user_input_clean = user_input.lower().strip().strip('?.!,')
        
        # 1. Simple hardcoded check for common greetings
        greetings = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "greetings", "yo", "sup"}
        if user_input_clean in greetings:
            return "GREETING"

        # 2. Default to TROUBLESHOOTING for all other queries to avoid slow LLM classification call on CPU
        return "TROUBLESHOOTING"
