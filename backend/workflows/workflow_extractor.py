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
from database.models import ExtractedWorkflow
from integrations.ollama_service import OllamaService

class WorkflowExtractor:
    def __init__(self):
        self.db: Session = SessionLocal()
        self.llm = OllamaService()

    async def extract_workflow(self, document_id: Any, text_content: str) -> Dict[str, Any]:
        """
        Takes raw document text, identifies the sequential workflow steps, parameters,
        and decision nodes, and registers the workflow in PostgreSQL.
        """
        logger.info(f"Extracting workflows from document content...")
        
        prompt = f"""
        You are an expert ITSM Workflow Architect. Analyze the following operational document text:
        ---
        {text_content[:8000]}
        ---
        
        Identify the core IT/support workflows, sequential steps, approval criteria, escalation limits, and parameter requirements described in the text.
        
        Generate a structured JSON representation of the extracted workflow using exactly this format:
        {{
            "workflow_name": "string (e.g. Asset Onboarding Workflow)",
            "domain": "string (one of: service_request_management, incident_management, approval_management, resolver_operations, teams_bot_operations)",
            "steps": [
                "Step 1: Description of what to check/do",
                "Step 2: Description of next action"
            ],
            "decision_nodes": [
                {{
                    "condition": "Condition statement (e.g. if manager approval is not found)",
                    "action": "Next action (e.g. query Active Directory manager mapping)"
                }}
            ],
            "required_parameters": [
                "parameter_name_1 (e.g. employee_email)",
                "parameter_name_2 (e.g. manager_name)"
            ]
        }}
        
        Return ONLY the raw JSON object. Do not include markdown code block syntax (like ```json), introduction, or conversational filler.
        """
        
        # Default fallback
        workflow_data = {
            "workflow_name": "Generic IT Workflow",
            "domain": "resolver_operations",
            "steps": ["Step 1: Check user description", "Step 2: Escalate if unresolved"],
            "decision_nodes": [],
            "required_parameters": ["user_query"]
        }
        
        try:
            response = await self.llm.generate_response(
                prompt=prompt,
                system_prompt="You are a strict JSON-only ITSM workflow extraction model. Respond with pure valid JSON only."
            )
            
            cleaned_response = response.strip()
            if "```json" in cleaned_response:
                cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_response:
                cleaned_response = cleaned_response.split("```")[1].split("```")[0].strip()
                
            parsed_data = json.loads(cleaned_response)
            workflow_data["workflow_name"] = parsed_data.get("workflow_name", workflow_data["workflow_name"])
            workflow_data["domain"] = parsed_data.get("domain", workflow_data["domain"])
            workflow_data["steps"] = parsed_data.get("steps", workflow_data["steps"])
            workflow_data["decision_nodes"] = parsed_data.get("decision_nodes", workflow_data["decision_nodes"])
            workflow_data["required_parameters"] = parsed_data.get("required_parameters", workflow_data["required_parameters"])
            
            logger.info(f"Successfully extracted workflow: {workflow_data['workflow_name']}")
        except Exception as e:
            logger.error(f"Error parsing workflow JSON: {e}. Falling back to default.")
            
        try:
            # Commit to database
            extracted = ExtractedWorkflow(
                document_id=document_id,
                workflow_name=workflow_data["workflow_name"],
                domain=workflow_data["domain"],
                steps=workflow_data["steps"],
                decision_nodes=workflow_data["decision_nodes"]
            )
            self.db.add(extracted)
            self.db.commit()
            logger.info(f"Saved extracted workflow '{extracted.workflow_name}' into PostgreSQL database.")
        except Exception as e:
            logger.error(f"Failed to save extracted workflow to PostgreSQL: {e}")
            self.db.rollback()
            
        return workflow_data

if __name__ == "__main__":
    import asyncio
    extractor = WorkflowExtractor()
    test_text = """
    ITSM SOP: Laptop Request Service Request
    1. Employee submits request for laptop (onboarding or upgrade).
    2. Check budget threshold: If price is > $1000, trigger Director Approval.
    3. Route to procurement team for laptop allocation and inventory tracking.
    Parameters needed: employee_email, laptop_model, price.
    """
    asyncio.run(extractor.extract_workflow(None, test_text))
