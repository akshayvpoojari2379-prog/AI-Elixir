import os
import sys
import json
from typing import Dict, Any
from loguru import logger

# Add backend directory to path
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from integrations.ollama_service import OllamaService

class IncidentSRClassifier:
    def __init__(self):
        self.llm = OllamaService()

    async def classify_ticket_type(self, query: str) -> Dict[str, Any]:
        """
        Dynamically analyzes the user issue to categorize it as:
        - "Incident" (something broken, outage, error, crash, failure)
        - "Service Request" (new access request, asset request, onboarding, upgrade)
        """
        logger.info("Running Incident vs Service Request Classification...")
        
        # Rule-based semantic pre-checks (highly performant and deterministic)
        query_lower = query.lower()
        incident_keywords = ["broken", "error", "fail", "timeout", "outage", "down", "crash", "stuck", "bug", "cannot login", "not working"]
        sr_keywords = ["request", "new laptop", "access", "onboard", "upgrade", "order", "need software", "install", "allocate", "replace", "replacement"]
        
        # Default fallback
        result = {
            "ticket_type": "Incident",
            "reason": "Defaulted based on standard support ticket heuristics.",
            "confidence": 0.6
        }
        
        # Perform rule matching
        inc_matches = sum(1 for kw in incident_keywords if kw in query_lower)
        sr_matches = sum(1 for kw in sr_keywords if kw in query_lower)
        
        if inc_matches > sr_matches:
            result["ticket_type"] = "Incident"
            result["reason"] = f"Deterministic rule matched operational keywords for Incident ({inc_matches} matches)."
            result["confidence"] = 0.95
            return result
        elif sr_matches > inc_matches:
            result["ticket_type"] = "Service Request"
            result["reason"] = f"Deterministic rule matched catalog requests keywords for Service Request ({sr_matches} matches)."
            result["confidence"] = 0.95
            return result
            
        # If ambiguous, use LLM reasoning
        prompt = f"""
        Analyze this user IT support query:
        "{query}"
        
        Classify this query into one of these two categories:
        1. "Incident" - If it describes an active issue, outage, broken system, failure, gateway timeout, crash, or password lockout.
        2. "Service Request" - If it describes a request for something new, onboarding, access provisioning, a laptop allocation, software installation, or budget approvals.
        
        Format the response strictly as a JSON object:
        {{
            "ticket_type": "Incident" or "Service Request",
            "reason": "concise explanation of why this classification was made",
            "confidence": 0.0 to 1.0 (float confidence score)
        }}
        
        Return ONLY valid JSON.
        """
        
        try:
            response = await self.llm.generate_response(
                prompt=prompt,
                system_prompt="You are a strict JSON-only ITSM classifier."
            )
            cleaned = response.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[1].split("```")[0].strip()
                
            parsed = json.loads(cleaned)
            ticket_type = parsed.get("ticket_type", "")
            if ticket_type in ["Incident", "Service Request"]:
                result["ticket_type"] = ticket_type
                result["reason"] = parsed.get("reason", result["reason"])
                result["confidence"] = float(parsed.get("confidence", 0.8))
                
            logger.info(f"LLM Classification: {result['ticket_type']} (Confidence: {result['confidence']})")
        except Exception as e:
            logger.error(f"Error classifying via LLM: {e}")
            
        return result

if __name__ == "__main__":
    import asyncio
    classifier = IncidentSRClassifier()
    print(asyncio.run(classifier.classify_ticket_type("Wi-Fi has a gateway timeout")))
    print(asyncio.run(classifier.classify_ticket_type("Requesting a MacBook Pro laptop for onboarding")))
