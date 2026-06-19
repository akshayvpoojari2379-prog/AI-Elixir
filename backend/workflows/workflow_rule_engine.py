import os
import sys
from typing import Dict, Any, List
from loguru import logger
from sqlalchemy.orm import Session

# Add backend directory to path
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from database.session import SessionLocal
from database.models import WorkflowRule

class WorkflowRuleEngine:
    def __init__(self):
        self.db: Session = SessionLocal()

    async def register_rule(self, skill_id: str, condition_name: str, condition_logic: Dict[str, Any], actions: List[str]) -> WorkflowRule:
        """Registers a structured executable rule linked to a dynamic skillset agent."""
        logger.info(f"Registering workflow rule for skill {skill_id}: '{condition_name}'")
        
        # Check if already exists
        existing = self.db.query(WorkflowRule).filter(
            WorkflowRule.skill_id == skill_id,
            WorkflowRule.condition_name == condition_name
        ).first()
        
        if existing:
            existing.condition_logic = condition_logic
            existing.actions = actions
            rule = existing
        else:
            rule = WorkflowRule(
                skill_id=skill_id,
                condition_name=condition_name,
                condition_logic=condition_logic,
                actions=actions
            )
            self.db.add(rule)
            
        self.db.commit()
        return rule

    async def evaluate_rules_for_agent(self, skill_id: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluates registered database rules and returns triggered actions
        and resolution/diagnostic messages.
        """
        logger.info(f"Evaluating rule engine conditions for skill agent '{skill_id}'...")
        
        rules = self.db.query(WorkflowRule).filter(
            WorkflowRule.skill_id == skill_id
        ).all()
        
        triggered_actions = []
        messages = []
        
        for rule in rules:
            logic = rule.condition_logic or {}
            param_key = logic.get("parameter")
            operator = logic.get("operator")
            comparison_value = logic.get("value")
            
            if not param_key or param_key not in variables:
                continue
                
            user_val = variables[param_key]
            is_matched = False
            
            # Perform operator evaluations
            if operator == "greater_than":
                try:
                    is_matched = float(user_val) > float(comparison_value)
                except ValueError:
                    pass
            elif operator == "equals":
                is_matched = str(user_val).strip().lower() == str(comparison_value).strip().lower()
            elif operator == "not_equals":
                is_matched = str(user_val).strip().lower() != str(comparison_value).strip().lower()
            elif operator == "contains":
                is_matched = str(comparison_value).strip().lower() in str(user_val).strip().lower()
                
            if is_matched:
                logger.info(f"Rule match triggered: '{rule.condition_name}'!")
                triggered_actions.extend(rule.actions)
                messages.append(f"Condition '{rule.condition_name}' matched. Executed: {', '.join(rule.actions)}.")
                
        # Proactive hardcoded fallback evaluation if no database rules are registered yet
        if not triggered_actions:
            # Check for standard approval logic
            if "price" in variables:
                try:
                    price = float(variables["price"])
                    if price > 1000:
                        triggered_actions.append("trigger_director_approval")
                        messages.append("Laptop cost exceeds $1000 threshold. Triggering Director approval flow.")
                except ValueError:
                    pass
            # Check for stuck ticket logic
            if "status" in variables and variables.get("status") == "pending_approval":
                triggered_actions.append("validate_reporting_manager")
                messages.append("Ticket is stuck pending approval. Triggering validation of Outlook reporting manager mapping.")

        return {
            "triggered": len(triggered_actions) > 0,
            "actions": triggered_actions,
            "diagnostic_messages": messages
        }

if __name__ == "__main__":
    import asyncio
    engine = WorkflowRuleEngine()
    # Test budget threshold rule evaluation
    res = asyncio.run(engine.evaluate_rules_for_agent("sr_workflow_agent", {"price": 1250}))
    print(res)
