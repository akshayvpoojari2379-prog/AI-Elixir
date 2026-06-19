import os
import sys
import json
import time
from typing import Dict, Any, List
from loguru import logger
from langgraph.graph import StateGraph, END

# Add backend directory to path
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from database.session import SessionLocal
from database.models import SkillRegistry, ChatSession, ChatMessage
from workflows.state import ServiceDeskState
from workflows.clarification_agent import ClarificationAgent
from workflows.incident_sr_classifier import IncidentSRClassifier
from workflows.workflow_rule_engine import WorkflowRuleEngine
from workflows.tools import ToolExecutionEngine
from workflows.ticket_automation_agent import TicketAutomationAgent
from services.observability_service import ObservabilityService
from integrations.ollama_service import OllamaService

class LangGraphWorkflows:
    def __init__(self):
        self.llm = OllamaService()
        self.clarification_agent = ClarificationAgent()
        self.classifier = IncidentSRClassifier()
        self.rule_engine = WorkflowRuleEngine()
        self.tool_executor = ToolExecutionEngine()
        self.ticket_automation = TicketAutomationAgent()
        self.observability = ObservabilityService()
        
        # Compile LangGraph State Machine
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(ServiceDeskState)

        # Define all nodes
        workflow.add_node("clarification_agent", self.run_clarification_agent)
        workflow.add_node("incident_sr_classifier", self.run_incident_sr_classifier)
        workflow.add_node("dynamic_skill_router", self.run_dynamic_skill_router)
        workflow.add_node("dynamic_skill_agent", self.run_dynamic_skill_agent)
        workflow.add_node("ticket_automation", self.run_ticket_automation)

        # Define starting entrypoint and standard routing edges
        workflow.set_entry_point("clarification_agent")

        # Routing logic from clarification
        workflow.add_conditional_edges(
            "clarification_agent",
            self.route_after_clarification,
            {
                "halt": END,
                "proceed": "incident_sr_classifier"
            }
        )

        # Proceed through classifier and router
        workflow.add_edge("incident_sr_classifier", "dynamic_skill_router")
        workflow.add_edge("dynamic_skill_router", "dynamic_skill_agent")

        # Routing logic after dynamic skillset execution
        workflow.add_conditional_edges(
            "dynamic_skill_agent",
            self.route_after_skill,
            {
                "resolve": END,
                "ticket_escalation": "ticket_automation"
            }
        )

        workflow.add_edge("ticket_automation", END)
        return workflow.compile()

    # ----------------- NODE IMPLEMENTATIONS -----------------

    async def run_clarification_agent(self, state: ServiceDeskState) -> Dict[str, Any]:
        """Node: Asks clarifying questions if required variables/slots are missing."""
        logger.info("Executing LangGraph clarification node...")
        res = await self.clarification_agent.run(state)
        return res

    def route_after_clarification(self, state: ServiceDeskState) -> str:
        """Determines if the graph should halt to ask user for slots or proceed."""
        if state.get("resolved", False):
            logger.info("LangGraph Route: Workflow resolved by Clarification Agent. Ending.")
            return "halt"
        if state.get("clarification_needed", False):
            logger.info("LangGraph Route: Clarification needed. Halting graph.")
            return "halt"
        logger.info("LangGraph Route: Slots verified. Proceeding to classification.")
        return "proceed"

    async def run_incident_sr_classifier(self, state: ServiceDeskState) -> Dict[str, Any]:
        """Node: Decides if the query is an Incident or a Service Request."""
        logger.info("Executing LangGraph Incident vs SR classification node...")
        
        # Check if skill is already matched and cached in state
        state_skill = state.get("skill")
        if state_skill:
            if state_skill == "incident_workflow":
                return {
                    "ticket_type": "incident",
                    "intent": "INCIDENT"
                }
            elif state_skill == "sr_workflow":
                return {
                    "ticket_type": "service_request",
                    "intent": "SERVICE_REQUEST"
                }
                
        query = state.get("query", "")
        res = await self.classifier.classify_ticket_type(query)
        
        return {
            "ticket_type": res["ticket_type"].lower().replace(" ", "_"),
            "intent": "SERVICE_REQUEST" if res["ticket_type"] == "Service Request" else "INCIDENT"
        }

    async def run_dynamic_skill_router(self, state: ServiceDeskState) -> Dict[str, Any]:
        """Node: Dynamically matches query against registered database skills."""
        logger.info("Executing LangGraph Dynamic Skill Router node...")
        start_time = time.time()
        
        query = state.get("query", "").lower()
        db = SessionLocal()
        
        matched_skill = None
        highest_conf = 0.5
        
        # Check if skill is already matched and cached in state
        state_skill = state.get("skill")
        if state_skill:
            if state_skill == "incident_workflow":
                matched_skill = "incident_management_agent"
                highest_conf = state.get("confidence", 0.9)
            elif state_skill == "sr_workflow":
                matched_skill = "service_request_management_agent"
                highest_conf = state.get("confidence", 0.9)
            else:
                matched_skill = state_skill
                highest_conf = state.get("confidence", 0.9)
                
        if not matched_skill:
            # Load all registered skill definitions from PostgreSQL
            skills = db.query(SkillRegistry).all()
            matched_skill = "general_agent"
            
            for skill in skills:
                # Match capabilities or domain keywords in query
                matches = 0
                for cap in skill.capabilities or []:
                    if str(cap).lower() in query:
                        matches += 1
                
                if matches > 0:
                    conf = 0.5 + (0.1 * matches)
                    if conf > highest_conf:
                        highest_conf = min(conf, 1.0)
                        matched_skill = skill.skill_id
                        
            # Specific semantic fallback defaults if not dynamically matched
            if matched_skill == "general_agent":
                if any(kw in query for kw in ["mouse", "keyboard", "printer", "scanner", "jam", "print", "scan", "crash", "hang", "boot", "working", "broken", "incident"]):
                    matched_skill = "incident_management_agent"
                else:
                    matched_skill = "service_request_management_agent"
                    
        latency = int((time.time() - start_time) * 1000)
        
        # Log to Observability routing table
        session_uuid = None
        try:
            from uuid import UUID
            session_uuid = UUID(state.get("session_id"))
        except Exception:
            pass
            
        await self.observability.log_routing_decision(
            session_id=session_uuid,
            query=state.get("query", ""),
            matched_skill=matched_skill,
            confidence_score=highest_conf,
            routing_history=state.get("routing_history", []) + ["dynamic_skill_router"],
            latency_ms=latency
        )
        
        # Load matched skill metadata
        sop_steps = []
        target_skill = db.query(SkillRegistry).filter(SkillRegistry.skill_id == matched_skill).first()
        if target_skill and target_skill.workflow_rules:
            raw_steps = target_skill.workflow_rules.get("steps", [])
            for step in raw_steps:
                if isinstance(step, dict):
                    desc = step.get("description", "")
                    action = step.get("action", "")
                    cond = step.get("condition", "")
                    parts = []
                    if desc:
                        parts.append(desc)
                    if cond:
                        parts.append(f"[Condition: {cond}]")
                    if action:
                        parts.append(f"[Action: {action}]")
                    sop_steps.append(" - ".join(parts) if parts else str(step))
                else:
                    sop_steps.append(str(step))
            
        db.close()
        
        routing_hist = state.get("routing_history", [])
        routing_hist.append("DynamicSkillRouter")
        
        return {
            "skill": matched_skill,
            "routing_history": routing_hist,
            "sop_steps": sop_steps,
            "confidence": highest_conf
        }

    async def run_dynamic_skill_agent(self, state: ServiceDeskState) -> Dict[str, Any]:
        """Node: Executes the dynamic skill prompt using step-by-step ReAct reasoning."""
        logger.info("Executing LangGraph Dynamic Skill ReAct Agent...")
        
        skill_id = state.get("skill", "service_request_management_agent")
        query = state.get("query", "")
        
        # Map skill key to registered agent skill ID if necessary
        if skill_id == "incident_workflow":
            skill_id = "incident_management_agent"
        elif skill_id == "sr_workflow":
            skill_id = "service_request_management_agent"
            
        db = SessionLocal()
        skill_data = db.query(SkillRegistry).filter(SkillRegistry.skill_id == skill_id).first()
        
        system_prompt = (
            "You are a helpful IT support assistant."
        )
        tools_registered = ["check_ticket_status"]
        
        if skill_data:
            system_prompt = skill_data.system_prompt
            tools_registered = skill_data.tools or tools_registered
            
        db.close()
        
        # Determine if ticket is needed: incidents or service requests always need a ticket
        is_workflow = skill_id in ["incident_management_agent", "service_request_management_agent"]
        ticket_needed = is_workflow or "approval" in query.lower() or "timeout" in query.lower() or "outage" in query.lower()
        
        routing_hist = state.get("routing_history", [])
        routing_hist.append("DynamicSkillAgent")
        
        if ticket_needed:
            logger.info("Ticket escalation is needed. Skipping LLM generation in dynamic skill agent.")
            return {
                "resolution": "Escalating to ticket automation...",
                "resolved": False,
                "ticket_needed": True,
                "routing_history": routing_hist
            }
            
        # 1. Evaluate registered operational rules (e.g. Budget check > 1000)
        variables = {
            "query": query,
            "cost": 1200 if "laptop" in query.lower() or "onboard" in query.lower() else 0,
            "price": 1200 if "laptop" in query.lower() or "onboard" in query.lower() else 0,
            "status": "pending_approval" if "stuck" in query.lower() or "approval" in query.lower() else "open"
        }
        
        rule_res = await self.rule_engine.evaluate_rules_for_agent(skill_id, variables)
        
        # 2. Run tools
        tool_results = []
        for tool_name in tools_registered:
            if "validate" in tool_name and "email" in query.lower():
                res = await self.tool_executor.execute("validate_reporting_manager", employee_email="employee@elixir.portal")
                tool_results.append(str(res))
            elif "stuck" in tool_name:
                res = await self.tool_executor.execute("analyze_ticket_stuck_reason", ticket_id="FS-ERR-999")
                tool_results.append(str(res))
            elif "chain" in tool_name:
                res = await self.tool_executor.execute("fetch_approval_chain", ticket_id="FS-ERR-999")
                tool_results.append(str(res))

        # 3. Request LLM response based on the dynamic prompt, rules, and tool outputs
        tool_outputs_str = "\n".join(tool_results)
        rule_messages_str = "\n".join(rule_res.get("diagnostic_messages", []))
        
        # Simplify system prompt for small model to prevent leaking the prompt
        if skill_data:
            clean_sys_prompt = f"You are a helpful IT support assistant specializing in {skill_data.domain_name}.\n"
            clean_sys_prompt += f"Help the user with queries related to: {skill_data.description}\n"
            clean_sys_prompt += "Provide a friendly, conversational, and direct response to the user's request. Keep it short."
        else:
            clean_sys_prompt = "You are a helpful IT support assistant."
            
        prompt = f"""
        User Request: "{query}"
        
        Rule Engine Notifications:
        {rule_messages_str}
        
        Active Tool Output Logs:
        {tool_outputs_str}
        
        Formulate a helpful IT Support response advising the user on what action has been taken,
        citing the relevant diagnostics. Suggest next steps.
        """
        
        response = await self.llm.generate_response(prompt, system_prompt=clean_sys_prompt)
        
        return {
            "resolution": response,
            "resolved": True,
            "ticket_needed": False,
            "routing_history": routing_hist
        }

    def route_after_skill(self, state: ServiceDeskState) -> str:
        """Determines if the issue is solved or if it requires automated ticketing."""
        if state.get("ticket_needed", False):
            logger.info("LangGraph Route: Issue unresolved or escalations triggered. Routing to Ticket Automation.")
            return "ticket_escalation"
        logger.info("LangGraph Route: Skill resolved successfully. Ending workflow.")
        return "resolve"

    async def run_ticket_automation(self, state: ServiceDeskState) -> Dict[str, Any]:
        """Node: Automates ticket dispatch in Freshservice for escalated queries."""
        logger.info("Executing LangGraph Ticket Automation node...")
        res = await self.ticket_automation.run(state)
        return res
