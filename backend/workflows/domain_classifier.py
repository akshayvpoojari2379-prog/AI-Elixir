import os
import sys
import json
from typing import Dict, Any, List
from loguru import logger
from sqlalchemy.orm import Session

# Add backend directory to path
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from database.session import SessionLocal
from database.models import OperationalDomain
from integrations.ollama_service import OllamaService

class DomainClassifier:
    def __init__(self):
        self.db: Session = SessionLocal()
        self.llm = OllamaService()

    async def classify_domain(self, text_content: str) -> Dict[str, Any]:
        """
        Classifies operational text into an enterprise support domain
        and registers the metadata in PostgreSQL.
        """
        logger.info("Classifying operational document domain...")
        
        prompt = f"""
        You are a smart IT Service Desk Classifier. Analyze this operational manual text:
        ---
        {text_content[:4000]}
        ---
        
        Classify this document into exactly one of these five core enterprise operational domains:
        - "service_request_management" (for onboarding, laptops requests, catalog items, asset request/allocation)
        - "incident_management" (for server down, broken Wi-Fi, application crash, network outage, incident ticket lifecycle)
        - "approval_management" (for approval chains, financial thresholds, reporting manager validations, pending approvals)
        - "resolver_operations" (for stuck tickets, debugging runbooks, resolver guidance, administrative SOPs)
        - "teams_bot_operations" (for Teams interactive commands, my tickets, Teams notifications/alerts, chat card actions)
        
        Provide a concise description of what the document covers, and list the key categories.
        
        Format the response strictly as a JSON object:
        {{
            "domain_name": "string (exactly one of the five listed above)",
            "description": "string (brief summary of this operational domain)",
            "categories": [
                "category_1",
                "category_2"
            ]
        }}
        
        Return ONLY raw JSON, with no markdown formatting.
        """
        
        # Fallback values
        domain_data = {
            "domain_name": "resolver_operations",
            "description": "ITSM Resolver guidance and stuck ticket operations",
            "categories": ["General Support", "Resolver Guidance"]
        }
        
        try:
            response = await self.llm.generate_response(
                prompt=prompt,
                system_prompt="You are a strict JSON-only ITSM domain classifier."
            )
            cleaned_response = response.strip()
            
            if "```json" in cleaned_response:
                cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_response:
                cleaned_response = cleaned_response.split("```")[1].split("```")[0].strip()
                
            parsed = json.loads(cleaned_response)
            # Ensure domain matches allowed
            allowed = ["service_request_management", "incident_management", "approval_management", "resolver_operations", "teams_bot_operations"]
            matched_domain = parsed.get("domain_name", "").lower().strip()
            if matched_domain in allowed:
                domain_data["domain_name"] = matched_domain
            domain_data["description"] = parsed.get("description", domain_data["description"])
            domain_data["categories"] = parsed.get("categories", domain_data["categories"])
            
            logger.info(f"Classified domain as: {domain_data['domain_name']}")
        except Exception as e:
            logger.error(f"Error classifying domain: {e}")
            
        try:
            # Save or update operational domain in Postgres
            existing = self.db.query(OperationalDomain).filter(
                OperationalDomain.domain_name == domain_data["domain_name"]
            ).first()
            
            if existing:
                existing.description = domain_data["description"]
                existing.categories = domain_data["categories"]
            else:
                new_domain = OperationalDomain(
                    domain_name=domain_data["domain_name"],
                    description=domain_data["description"],
                    categories=domain_data["categories"]
                )
                self.db.add(new_domain)
                
            self.db.commit()
            logger.info(f"Persisted Operational Domain '{domain_data['domain_name']}' in PostgreSQL.")
        except Exception as e:
            logger.error(f"Failed to persist operational domain to Postgres: {e}")
            self.db.rollback()
            
        return domain_data

if __name__ == "__main__":
    import asyncio
    classifier = DomainClassifier()
    asyncio.run(classifier.classify_domain("How to restart Wi-Fi router when DNS is stuck"))
