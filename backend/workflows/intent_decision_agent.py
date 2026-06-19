import json
from typing import Dict, Any
from loguru import logger
from integrations.ollama_service import OllamaService
from workflows.state import ServiceDeskState
from workflows.knowledge_engine import KnowledgeEngine

class IntentDecisionAgent:
    def __init__(self):
        self.llm = OllamaService()
        self.kb_engine = KnowledgeEngine()

    async def run(self, state: ServiceDeskState) -> Dict[str, Any]:
        """
        Intent + Ticket Type Decision Agent:
        1. Classifies the query/issue into FAQ_QUERY, KNOWLEDGE_GUIDANCE, INCIDENT, SERVICE_REQUEST, or ESCALATION.
        2. Merges rule-based workflow rules with LLM reasoning.
        """
        logger.info("Running Intent + Ticket Type Decision Agent...")
        query = state.get("query", "")
        skill = state.get("skill")
        issue_type = state.get("issue_type")
        routing_history = state.get("routing_history", [])
        routing_history.append("IntentDecisionAgent")

        # 1. Rule-Based Determination if we matched a specific issue
        rule_intent = None
        rule_confidence = 0.0

        if skill and issue_type:
            skill_details = self.kb_engine.get_skill_details(skill)
            issue_details = skill_details.get("issues", {}).get(issue_type, {})
            t_type = issue_details.get("ticket_type")
            
            if t_type:
                logger.info(f"Rule-based ticket type found in knowledge base: {t_type}")
                rule_intent = t_type.upper()
                rule_confidence = 1.0 # Exact mapping in KB

        # 2. LLM-Based Reasoning for classification (if no exact rule, or to validate rules)
        # We classify user queries into: FAQ, INCIDENT, SERVICE_REQUEST, ESCALATION, or KNOWLEDGE
        prompt = f"""
        Classify the following user query for an enterprise IT / operations support desk.
        Query: "{query}"
        Matched Skill: "{skill or 'None'}"
        Matched Issue: "{issue_type or 'None'}"
        
        Enterprise Definition Guidelines:
        - INCIDENT: Reporting something broken, error messages, connection failure, system crash, unexpected timeouts (e.g., VPN outage, application crash, Teams bot command error).
        - SERVICE_REQUEST: Requesting something new, access provisioning, hardware updates, executing an operational runbook, scheduling maintenance (e.g., software license access, device provisioning, database restore runbook, server patching).
        - FAQ_QUERY: Asking simple general questions that do not require an active ticket or manual intervention (e.g., standard matrix rules, where to check approvals).
        - ESCALATION: User is angry, frustrated, or explicitly requesting a human agent / supervisor.
        
        Respond with a JSON object in this format:
        {{
            "ticket_type": "incident" | "service_request" | "faq" | "escalation",
            "confidence": 0.0 to 1.0,
            "reason": "Brief explanation"
        }}
        
        Ensure you only return the raw JSON object and nothing else.
        """
        
        llm_intent = "faq"
        llm_confidence = 0.5
        
        try:
            response = await self.llm.generate_response(prompt, system_prompt="You are a JSON-only intent classification system.")
            cleaned_response = response.strip()
            
            # Extract JSON from potential Markdown formatting
            if "```json" in cleaned_response:
                cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_response:
                cleaned_response = cleaned_response.split("```")[1].split("```")[0].strip()
                
            data = json.loads(cleaned_response)
            llm_intent = data.get("ticket_type", "faq").upper()
            llm_confidence = data.get("confidence", 0.7)
            logger.info(f"LLM Classification: {llm_intent} with confidence {llm_confidence}")
        except Exception as e:
            logger.error(f"Error parsing LLM intent classification: {str(e)}")

        # 3. Combine classifications: rule-based takes priority if confidence is high
        final_intent = rule_intent if (rule_intent and rule_confidence > 0.8) else llm_intent
        final_confidence = rule_confidence if (rule_intent and rule_confidence > 0.8) else llm_confidence

        # If escalation is detected, trigger ticket needed immediately
        ticket_needed = False
        if final_intent in ["INCIDENT", "SERVICE_REQUEST", "ESCALATION"]:
            ticket_needed = True

        logger.info(f"Final Decision: intent={final_intent}, confidence={final_confidence}, ticket_needed={ticket_needed}")

        return {
            "intent": final_intent,
            "ticket_type": final_intent.lower() if final_intent in ["INCIDENT", "SERVICE_REQUEST"] else "incident",
            "confidence": final_confidence,
            "ticket_needed": ticket_needed,
            "routing_history": routing_history
        }
