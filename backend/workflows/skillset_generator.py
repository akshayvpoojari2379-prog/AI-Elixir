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
from database.models import SkillRegistry
from integrations.ollama_service import OllamaService

class SkillsetGenerator:
    def __init__(self):
        self.db: Session = SessionLocal()
        self.llm = OllamaService()

    async def generate_skillset(self, workflow_data: Dict[str, Any], domain_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dynamically crafts and registers an autonomous skill agent prompt, capabilities,
        and tool registrations in PostgreSQL.
        """
        logger.info(f"Generating dynamic skillset for domain: {domain_data['domain_name']}...")
        
        domain = domain_data["domain_name"]
        workflow_name = workflow_data["workflow_name"]
        steps_str = "\n".join([f"- {step}" for step in workflow_data.get("steps", [])])
        
        # Determine dynamic tools to bind to this skill domain
        tools = ["check_ticket_status"]
        if domain == "approval_management":
            tools.extend(["fetch_approval_chain", "validate_reporting_manager", "get_assignment_group"])
        elif domain == "service_request_management":
            tools.extend(["create_service_request", "get_assignment_group"])
        elif domain == "incident_management":
            tools.extend(["create_incident", "get_assignment_group"])
        elif domain == "resolver_operations":
            tools.extend(["analyze_ticket_stuck_reason", "fetch_approval_chain", "validate_reporting_manager"])
        elif domain == "teams_bot_operations":
            tools.extend(["check_ticket_status", "create_incident"])
            
        # Call LLM to generate a premium system prompt for this ReAct agent
        prompt = f"""
        You are an expert ITSM Prompt Engineer. Design a professional, premium ReAct system prompt for an IT Support Assistant specializing in the following domain:
        ---
        Domain: {domain}
        Workflow: {workflow_name}
        Core SOP Steps:
        {steps_str}
        Registered Tools: {tools}
        ---
        
        The system prompt must:
        1. Instruct the AI on how to reason step-by-step using ReAct.
        2. Advise the user conversationally.
        3. Enforce slot clarification: Ask the user for missing variables before routing or calling tools.
        4. Detail the SOP checklist and tell the agent how to evaluate the steps.
        
        Write a concise, professional system prompt of about 3-4 paragraphs. Enforce that the agent must only advise on topics related to this specific workflow and domain.
        
        Return ONLY the generated system prompt. Do not include markdown formatting or chat wrappers.
        """
        
        system_prompt = f"You are a specialized agent for {domain}. Help users with {workflow_name} workflows using these steps:\n{steps_str}"
        
        try:
            generated_prompt = await self.llm.generate_response(
                prompt=prompt,
                system_prompt="You are a professional Prompt Engineering Assistant."
            )
            if generated_prompt.strip():
                system_prompt = generated_prompt.strip()
            logger.info("Successfully generated dynamic agent prompt.")
        except Exception as e:
            logger.error(f"Error generating system prompt: {e}")
            
        skill_id = f"{domain}_agent"
        skill_desc = f"Autonomous ReAct agent for {workflow_name} under {domain}."
        
        # Capabilities based on steps
        capabilities = workflow_data.get("required_parameters", []) + domain_data.get("categories", [])
        
        skill_record = {
            "skill_id": skill_id,
            "domain_name": domain,
            "description": skill_desc,
            "capabilities": capabilities,
            "workflow_rules": {
                "workflow_name": workflow_name,
                "steps": workflow_data.get("steps", []),
                "decision_nodes": workflow_data.get("decision_nodes", [])
            },
            "system_prompt": system_prompt,
            "tools": tools,
            "escalation_rules": {
                "default_priority": 2, # Medium
                "escalation_group": "IT Support Desk"
            }
        }
        
        try:
            # Commit to skill_registry table
            existing = self.db.query(SkillRegistry).filter(
                SkillRegistry.skill_id == skill_id
            ).first()
            
            if existing:
                existing.domain_name = skill_record["domain_name"]
                existing.description = skill_record["description"]
                existing.capabilities = skill_record["capabilities"]
                existing.workflow_rules = skill_record["workflow_rules"]
                existing.system_prompt = skill_record["system_prompt"]
                existing.tools = skill_record["tools"]
                existing.escalation_rules = skill_record["escalation_rules"]
            else:
                new_skill = SkillRegistry(
                    skill_id=skill_record["skill_id"],
                    domain_name=skill_record["domain_name"],
                    description=skill_record["description"],
                    capabilities=skill_record["capabilities"],
                    workflow_rules=skill_record["workflow_rules"],
                    system_prompt=skill_record["system_prompt"],
                    tools=skill_record["tools"],
                    escalation_rules=skill_record["escalation_rules"]
                )
                self.db.add(new_skill)
                
            self.db.commit()
            logger.info(f"Dynamically registered Skill Agent '{skill_id}' in skill_registry PostgreSQL table.")
        except Exception as e:
            logger.error(f"Failed to commit skill registry record: {e}")
            self.db.rollback()
            
        return skill_record

if __name__ == "__main__":
    import asyncio
    generator = SkillsetGenerator()
    asyncio.run(generator.generate_skillset(
        {"workflow_name": "Reset Password", "steps": ["Check identity", "Reset in AD"]},
        {"domain_name": "resolver_operations", "categories": ["Password"]}
    ))
