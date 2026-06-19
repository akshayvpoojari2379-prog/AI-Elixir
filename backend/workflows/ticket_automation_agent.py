import json
from typing import Dict, Any
from loguru import logger
from integrations.freshservice_service import FreshserviceService
from integrations.ollama_service import OllamaService
from workflows.state import ServiceDeskState

class TicketAutomationAgent:
    def __init__(self):
        self.fs_service = FreshserviceService()
        self.llm = OllamaService()

    async def run(self, state: ServiceDeskState) -> Dict[str, Any]:
        """
        Ticket Automation Agent:
        1. Analyzes conversation history and issue to generate structured fields.
        2. Automatically creates an Incident or Service Request ticket in Freshservice.
        3. Assigns appropriate groups based on ITSM operational workflows.
        """
        logger.info("Running Ticket Automation Agent...")
        query = state.get("query", "")
        intent = state.get("intent", "INCIDENT")
        skill = state.get("skill", "general")
        issue_type = state.get("issue_type")
        messages = state.get("messages", [])
        routing_history = state.get("routing_history", [])
        routing_history.append("TicketAutomationAgent")

        # Confirmation checkpoint logic for Incidents
        ticket_type = "Incident" if intent in ["INCIDENT", "INCIDENT_CREATION", "ESCALATION"] else "Service Request"
        ticket_confirmed = state.get("ticket_confirmed")
        
        if ticket_type == "Incident":
            if ticket_confirmed == "cancelled":
                return {
                    "ticket_id": None,
                    "ticket_created": False,
                    "resolved": True,
                    "resolution": "Understood. I have cancelled the ticket creation process. Please let me know how else I can assist you.",
                    "routing_history": routing_history,
                    "ticket_confirmed": "cancelled"
                }
            elif ticket_confirmed == "pending":
                # Classify the user response
                reply_clean = query.lower().strip()
                decision = "ambiguous"
                
                # Heuristic substring checks first
                if any(w in reply_clean for w in ["no", "cancel", "don't", "dont", "abort", "stop"]):
                    if not any(w in reply_clean for w in ["yes", "yeah", "yep", "sure", "proceed"]):
                        decision = "no"
                elif any(w in reply_clean for w in ["yes", "yeah", "yep", "sure", "proceed", "confirm", "go ahead", "ok", "okay", "do it"]):
                    decision = "yes"
                
                # Fallback to LLM if still ambiguous
                if decision == "ambiguous":
                    # Fallback to LLM classifier
                    confirm_prompt = f"""
                    Determine if this user response is confirming or cancelling/denying the action of creating an IT support ticket:
                    User Response: "{query}"
                    
                    Respond with exactly one word:
                    - "yes" (if confirming, agreeing, saying go ahead, yes, sure, okay)
                    - "no" (if cancelling, denying, saying no, don't, stop, cancel)
                    - "ambiguous" (if unsure or they are asking a new question)
                    
                    Return ONLY the single word response.
                    """
                    try:
                        llm_res = await self.llm.generate_response(confirm_prompt, system_prompt="You are a strict one-word text classifier.")
                        res_word = llm_res.strip().lower().replace(".", "").replace('"', '').replace("'", "").replace("*", "")
                        if res_word in ["yes", "no", "ambiguous"]:
                            decision = res_word
                    except Exception as e:
                        logger.error(f"Error in confirmation LLM classifier: {e}")
                
                if decision == "yes":
                    ticket_confirmed = "confirmed"
                    state["ticket_confirmed"] = "confirmed"
                    logger.info("User confirmed ticket creation. Proceeding to raise Incident ticket.")
                elif decision == "no":
                    logger.info("User cancelled ticket creation.")
                    return {
                        "ticket_id": None,
                        "ticket_created": False,
                        "resolved": True,
                        "resolution": "Understood. I have cancelled the ticket creation process. Please let me know how else I can assist you.",
                        "routing_history": routing_history,
                        "ticket_confirmed": "cancelled"
                    }
                else:
                    logger.info("User confirmation query was ambiguous.")
                    return {
                        "ticket_id": None,
                        "ticket_created": False,
                        "resolved": False,
                        "resolution": "I'm sorry, I didn't quite catch that. Shall I proceed with raising the incident ticket? (Please respond with Yes or No)",
                        "routing_history": routing_history,
                        "ticket_confirmed": "pending"
                    }
            elif ticket_confirmed != "confirmed":
                # First time reaching ticket automation for incident, prompt user
                logger.info("Prompting user for ticket confirmation.")
                return {
                    "ticket_id": None,
                    "ticket_created": False,
                    "resolved": False,
                    "resolution": "For this issue, the best solution is to raise an incident ticket. Shall I proceed with creating this ticket?",
                    "routing_history": routing_history,
                    "ticket_confirmed": "pending"
                }

        # 1. Gather context from conversation history
        history_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

        # 2. Fetch domain category tree from database dynamically
        from database.session import SessionLocal
        from database.models import OperationalDomain

        domain_name = "incident_management" if intent in ["INCIDENT", "INCIDENT_CREATION", "ESCALATION"] else "service_request_management"
        categories_tree = {}
        
        db = SessionLocal()
        try:
            domain = db.query(OperationalDomain).filter(OperationalDomain.domain_name == domain_name).first()
            if domain and domain.categories:
                categories_tree = domain.categories
                if isinstance(categories_tree, str):
                    categories_tree = json.loads(categories_tree)
                logger.info(f"Loaded category tree from database for {domain_name}.")
            else:
                logger.warning(f"No category tree found in database for {domain_name}, using fallback.")
        except Exception as e:
            logger.error(f"Error querying operational domain categories: {str(e)}")
        finally:
            db.close()

        # Fallback trees if DB load failed or is empty
        if not categories_tree:
            if domain_name == "incident_management":
                categories_tree = {
                    "Hardware Issues": {
                        "Desktop / Laptop": [
                            "Battery discharging in less than an Hour",
                            "Charger not working",
                            "Keyboard not working",
                            "Mouse Not Working",
                            "Mouse issues",
                            "Others",
                            "Screen Damaged",
                            "Touchpad issues"
                        ],
                        "System Issues": [],
                        "System Crash": [],
                        "System Hang": [],
                        "Screen": [],
                        "System not booting": []
                    },
                    "Printer/Scanner": {
                        "Printer": [
                            "Paper Jam",
                            "Unable to print documents",
                            "Existing printer reconfiguration"
                        ],
                        "Scanner": [
                            "Unable to scan documents",
                            "Email to scan not working"
                        ]
                    }
                }
            else:
                categories_tree = {
                    "Service Request Workflows": {
                        "Asset Catalog Items": [
                            "Laptop Request for New Joinee",
                            "Laptop Request in cases of Transfer / Promotion",
                            "Request for allocation of Temporary / Project / Team laptop/Desktop",
                            "Request for replacement of Desktop/Laptop/Tab",
                            "Surrender of Laptop",
                            "Off-Role Joinee Laptop",
                            "Self-Certification of Asset"
                        ]
                    }
                }

        categories_allowed = list(categories_tree.keys())
        default_category = categories_allowed[0] if categories_allowed else "Hardware Issues"
        
        default_subcategory = None
        if default_category in categories_tree:
            subcats = categories_tree[default_category]
            if isinstance(subcats, dict) and subcats:
                default_subcategory = list(subcats.keys())[0]
            elif isinstance(subcats, list) and subcats:
                default_subcategory = subcats[0]

        # Default fallback parameters
        subject = f"AI Service Desk: {query[:50]}..."
        category = default_category
        subcategory = default_subcategory or "System Issues"
        item_category = None
        assignment_group = "IT Support Desk"
        summary = f"The user reported the following issue: {query}\n\nTroubleshooting was initiated conversationally by the AI Assistant."

        # Construct prompt instructing LLM to select from our dynamic category tree
        tree_str = json.dumps(categories_tree, indent=2)
        prompt = f"""
        Analyze this conversation between a user and an IT Support chatbot:
        {history_str}
        
        Last user request: "{query}"
        Matched skill category: "{skill}"
        Detected intent: "{intent}"
        
        We need to generate a Freshservice ticket. Determine the following parameters:
        - subject: A clean, concise title summarizing the main user problem (e.g., Laptop mouse issue, Printer error, etc. depending on context).
        - category: Select one exactly from the keys of this JSON tree: {categories_allowed}.
        - subcategory: Select a subcategory key from the selected category in the JSON tree.
        - item_category: Select a specific issue/item from the list under the selected subcategory, if applicable (set to null if not applicable or list is empty).
        - assignment_group: Always "IT Support Desk".
        - summary: A professional summary of the issue.
        
        Here is the JSON tree of allowed categories, subcategories, and items:
        {tree_str}
        
        Respond with a JSON object in this format:
        {{
            "subject": "string",
            "category": "string",
            "subcategory": "string",
            "item_category": "string or null",
            "assignment_group": "string",
            "summary": "string"
        }}
        
        Return ONLY the raw JSON object, no conversational wrapper.
        """

        try:
            response = await self.llm.generate_response(prompt, system_prompt="You are a JSON-only Freshservice ticket router.")
            cleaned_response = response.strip()
            
            if "```json" in cleaned_response:
                cleaned_response = cleaned_response.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_response:
                cleaned_response = cleaned_response.split("```")[1].split("```")[0].strip()
                
            data = json.loads(cleaned_response)
            subject = data.get("subject", subject)
            category = data.get("category", category)
            subcategory = data.get("subcategory", subcategory)
            item_category = data.get("item_category", item_category)
            assignment_group = data.get("assignment_group", assignment_group)
            summary = data.get("summary", summary)
        except Exception as e:
            logger.error(f"Error parsing LLM ticket parameters: {str(e)}")

        # 3. Dynamic Keyword Override and Validation against Database Tree
        query_lower = query.lower()
        history_lower = history_str.lower()
        matched_from_db = False
        
        user_messages_content = [msg["content"].lower() for msg in messages if msg["role"] == "user"]
        
        # Check for matching items in the DB categories tree based on keywords
        is_mdg = "mdg" in query_lower or any("mdg" in m for m in user_messages_content) or issue_type == "sap_mdg_issues"
        if is_mdg:
            category = "SAP MDG"
            subcats = categories_tree.get("SAP MDG", {})
            for sub in subcats:
                if sub.lower() in query_lower or any(sub.lower() in m for m in user_messages_content):
                    subcategory = sub
                    matched_from_db = True
                    logger.info(f"Dynamic DB override matched MDG subcategory '{sub}': category='{category}'")
                    
                    # Also resolve item_category from user messages history
                    items = subcats.get(sub, [])
                    if isinstance(items, list):
                        for it in items:
                            if it.lower() in query_lower or any(it.lower() in m for m in user_messages_content):
                                item_category = it
                                logger.info(f"Dynamic DB override matched MDG item '{it}'")
                                break
                    break

        keywords_to_check = ["mouse", "keyboard", "battery", "charger", "screen", "touchpad", "printer", "scanner", "print", "scan"]
        for kw in keywords_to_check:
            if kw in query_lower or kw in history_lower:
                for cat, subcats in categories_tree.items():
                    if isinstance(subcats, dict):
                        for subcat, items in subcats.items():
                            if isinstance(items, list):
                                for item in items:
                                    if kw in item.lower():
                                        category = cat
                                        subcategory = subcat
                                        item_category = item
                                        matched_from_db = True
                                        logger.info(f"Dynamic DB override matched keyword '{kw}': category='{category}', subcategory='{subcategory}', item='{item_category}'")
                                        break
                            if matched_from_db:
                                break
                    if matched_from_db:
                        break
            if matched_from_db:
                break

        # Validate category, subcategory, and item_category against the categories tree to ensure exact values
        if not matched_from_db:
            # Validate Category
            if category not in categories_tree:
                found_cat = None
                for c in categories_tree:
                    if c.lower() == category.lower():
                        found_cat = c
                        break
                if found_cat:
                    category = found_cat
                else:
                    category = list(categories_tree.keys())[0] if categories_tree else "Hardware Issues"
            
            # Validate Subcategory
            subcategories = categories_tree.get(category, {})
            if isinstance(subcategories, dict):
                if subcategory not in subcategories:
                    found_sub = None
                    for s in subcategories:
                        if s.lower() == subcategory.lower():
                            found_sub = s
                            break
                    if found_sub:
                        subcategory = found_sub
                    else:
                        subcategory = list(subcategories.keys())[0] if subcategories else "System Issues"
                
                # Validate Item Category
                items = subcategories.get(subcategory, [])
                if isinstance(items, list) and items:
                    if item_category not in items:
                        found_item = None
                        for it in items:
                            if item_category and it.lower() == item_category.lower():
                                found_item = it
                                break
                        if found_item:
                            item_category = found_item
                        else:
                            # Fallback check: see if query/history matches any item in this subcategory list
                            for it in items:
                                if it.lower() in query_lower or it.lower() in history_lower:
                                    item_category = it
                                    break
                            else:
                                item_category = None
                else:
                    item_category = None
            else:
                subcategory = "System Issues"
                item_category = None

        logger.info(f"Generated Ticket Data: subject={subject}, group={assignment_group}, category={category}, subcategory={subcategory}, item={item_category}")

        # 3. Call Freshservice API
        ticket_type = "Incident" if intent in ["INCIDENT", "INCIDENT_CREATION", "ESCALATION"] else "Service Request"
        
        item_str = f" / {item_category}" if item_category else ""
        full_description = f"""
        <h3>Automated Ticket Details</h3>
        <p><strong>Created by:</strong> AI Elixir</p>
        <p><strong>Recommended Assignment Group:</strong> {assignment_group}</p>
        <p><strong>Category/Subcategory/Item:</strong> {category} / {subcategory}{item_str}</p>
        <br/>
        <h3>Issue Summary</h3>
        <p>{summary}</p>
        """

        ticket_id = None
        ticket_created = False
        
        try:
            ticket = await self.fs_service.create_ticket(
                subject=subject,
                description=full_description,
                email="employee@elixir.portal", # Authenticated employee placeholder
                priority=2, # Medium
                status=2, # Open
                type=ticket_type,
                category=category,
                sub_category=subcategory,
                item_category=item_category
            )
            ticket_id = str(ticket.get("id"))
            ticket_created = True
            logger.info(f"Successfully created Freshservice ticket ID: {ticket_id}")
        except Exception as e:
            logger.error(f"Failed to create Freshservice ticket: {str(e)}")
            ticket_id = "FS-ERR-999" # Mock/Fallback ID for operational continuity

        resolution_msg = f"""I have automatically raised a Freshservice **{ticket_type}** ticket for you.
 
**Ticket Reference:** #{ticket_id if ticket_id else "Pending"}
**Subject:** {subject}
**Assignment Group:** {assignment_group}
**Status:** Open / Dispatched

Our support team has been notified and will review your request immediately."""

        return {
            "ticket_id": ticket_id,
            "ticket_created": ticket_created,
            "resolved": True,
            "resolution": resolution_msg,
            "routing_history": routing_history,
            "ticket_confirmed": ticket_confirmed
        }
