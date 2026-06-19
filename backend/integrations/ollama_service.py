import httpx
import json
from typing import Dict, Any, Generator, Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings
from prompts.rag_prompts import SYSTEM_PROMPT

class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.MODEL_NAME
        self.timeout = httpx.Timeout(600.0)
        self.gemini_api_key = settings.GEMINI_API_KEY
        self.gemini_model = settings.GEMINI_MODEL_NAME

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def generate_response(self, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        """Generate a complete response from Gemini (with fallback/commented-out Ollama logic)."""
        if self.gemini_api_key:
            logger.info(f"Generating response from Gemini using model {self.gemini_model}...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.gemini_model}:generateContent?key={self.gemini_api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.1
                },
                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                }
            }
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    candidates = result.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {})
                        parts = content.get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
                    return ""
                except Exception as e:
                    logger.error(f"Error communicating with Gemini: {str(e)}")
                    return "The Gemini API service is currently unavailable. Please try again later."
        else:
            # Gemma / Local Ollama model logic (commented out/disabled by user request)
            # logger.info(f"Generating response from Ollama using model {self.model}...")
            # payload = {
            #     "model": self.model,
            #     "prompt": prompt,
            #     "system": system_prompt,
            #     "stream": False,
            #     "options": {
            #         "temperature": 0.1,
            #     }
            # }
            # async with httpx.AsyncClient(timeout=self.timeout) as client:
            #     response = await client.post(f"{self.base_url}/api/generate", json=payload)
            #     response.raise_for_status()
            #     result = response.json()
            #     return result.get("response", "")
            logger.warning("Gemini API key is not configured and Gemma/Ollama is commented out.")
            return "AI model service is not configured correctly."

    async def generate_stream(self, prompt: str, system_prompt: str = SYSTEM_PROMPT) -> Generator[str, None, None]:
        """Generate a streaming response from Gemini (with fallback/commented-out Ollama logic)."""
        if self.gemini_api_key:
            logger.info(f"Starting response streaming from Gemini using model {self.gemini_model}...")
            # Yield the full content as a single chunk to be safe and robust
            full_text = await self.generate_response(prompt, system_prompt)
            yield full_text
        else:
            # Gemma / Local Ollama streaming logic (commented out/disabled by user request)
            # logger.info(f"Starting streaming response from Ollama using model {self.model}...")
            # payload = {
            #     "model": self.model,
            #     "prompt": prompt,
            #     "system": system_prompt,
            #     "stream": True,
            #     "options": {
            #         "temperature": 0.1,
            #     }
            # }
            # async with httpx.AsyncClient(timeout=self.timeout) as client:
            #     async with client.stream("POST", f"{self.base_url}/api/generate", json=payload) as response:
            #         response.raise_for_status()
            #         async for line in response.aiter_lines():
            #             if line:
            #                 data = json.loads(line)
            #                 if "response" in data:
            #                     yield data["response"]
            yield "\n[Error: AI model service is not configured correctly.]"
