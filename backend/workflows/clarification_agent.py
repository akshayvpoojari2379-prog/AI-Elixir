from typing import Dict, Any, List
from loguru import logger
from integrations.ollama_service import OllamaService
from workflows.state import ServiceDeskState
from workflows.knowledge_engine import KnowledgeEngine

class ClarificationAgent:
    def __init__(self):
        self.llm = OllamaService()
        self.kb_engine = KnowledgeEngine()

    async def run(self, state: ServiceDeskState) -> Dict[str, Any]:
        """
        Clarification Agent:
        1. Analyzes the user's query and history.
        2. Tries to match a workflow/sub-issue.
        3. Gathers missing details based on the workflow's clarification questions.
        4. If a clarification question is unanswered, ask it!
        """
        logger.info("Running Clarification Agent...")
        query = state.get("query", "")
        session_id = state.get("session_id", "")
        messages = state.get("messages", [])
        
        # Initialize answers and history tracking if not present
        clarification_answers = state.get("clarification_answers", {})
        if clarification_answers is None:
            clarification_answers = {}
            
        routing_history = state.get("routing_history", [])
        routing_history.append("ClarificationAgent")

        # Join previous messages to detect if answers were already provided
        full_conversation = "\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

        # Step 1: Query matchmaking via KnowledgeEngine
        skill = state.get("skill")
        issue_type = state.get("issue_type")
        match_conf = state.get("confidence", 0.0)
        
        if not skill or not issue_type:
            skill, issue_type, match_conf = self.kb_engine.match_workflow(query)
            logger.info(f"Knowledge Match: skill={skill}, issue={issue_type}, confidence={match_conf}")
        else:
            logger.info(f"Reusing existing workflow context from state: skill={skill}, issue={issue_type}")

        if not skill or not issue_type or match_conf < 0.35:
            # Try to resolve query via RAG database first
            from database.session import SessionLocal
            from rag.rag_pipeline import RAGPipeline
            
            db_session = SessionLocal()
            try:
                rag_pipeline = RAGPipeline(db_session)
                rag_res = await rag_pipeline.process_query(query, session_history=messages)
                
                # Check if RAG found a valid match with a confidence score >= 0.55
                if rag_res.get("confidence", 0.0) >= 0.55:
                    logger.info(f"Resolved via RAG: confidence={rag_res['confidence']}")
                    return {
                        "resolution": rag_res["response"],
                        "resolved": True,
                        "clarification_needed": False,
                        "routing_history": routing_history,
                        "confidence": rag_res["confidence"],
                        "sources": rag_res.get("sources", [])
                    }
            except Exception as re:
                logger.error(f"Error during RAG search fallback: {re}")
            finally:
                db_session.close()

            # Check if query is unrelated to IT support using binary classification
            classification_prompt = f"""Is the following query related to corporate IT support, software, hardware, office equipment, general technology, or is it a greeting/casual chat (hi, hello)?
Query: "{query}"
Respond with exactly 'yes' or 'no':"""
            try:
                class_res = await self.llm.generate_response(classification_prompt, system_prompt="You are a strict binary classifier. Respond ONLY with 'yes' or 'no'.")
                logger.info(f"Unrelated query check for '{query}': response='{class_res.strip()}'")
                clean_res = class_res.lower().strip()
                if "no" in clean_res and "yes" not in clean_res:
                    return {
                        "resolution": "I am sorry, but I do not have relevant information regarding this request. As the IT Support Assistant, I can only assist with corporate IT support, software provisioning, and hardware/asset requests. Please let me know if you have any IT-related questions!",
                        "clarification_needed": True,
                        "routing_history": routing_history,
                        "confidence": match_conf
                    }
            except Exception as e:
                logger.error(f"Error classifying query relevance: {e}")

            # Query is highly ambiguous or doesn't match a clear operational path.
            # Use LLM to understand what they are asking about and suggest options.
            logger.info("Low confidence in exact workflow. Asking LLM to clarify or select category.")
            
            # Extract last few messages for conversation history context
            history_context = ""
            if messages:
                history_context = "Recent conversation history:\n" + "\n".join([f"{m['role']}: {m['content']}" for m in messages[-4:]]) + "\n"

            prompt = f"""
            {history_context}
            User's latest message: "{query}"
            
            This is an enterprise IT/Support system.
            1. If the user's message is a greeting or casual chat, greet them back and ask how you can help with their IT support needs today.
            2. If the user's message is completely unrelated to IT support, office equipment, software access, or corporate workflows (e.g., general trivia, recipes, unrelated personal chatter), do NOT ask them about IT systems. Instead, politely explain that you are the IT Support Assistant and can only assist with corporate IT support, software provisioning, and hardware requests.
            3. Otherwise, if the request is related to IT/support but is too vague or ambiguous, generate a helpful, conversational response asking the user to describe their issue in more detail (for example, asking which application or hardware they are having trouble with).
            Keep it brief, professional, and friendly. Do not mention internal workflow categories or technical domain names.
            """
            response = await self.llm.generate_response(prompt, system_prompt="You are an enterprise service desk clarification assistant.")
            
            return {
                "resolution": response,
                "clarification_needed": True,
                "routing_history": routing_history,
                "confidence": match_conf
            }

        # Step 2: Intercept for Asset Management / Dynamic Service Request workflows
        if issue_type in ["asset_allocation_surrender", "mdg_service_request", "account_unlock_service_request", "password_reset_service_request"]:
            logger.info(f"Intercepting for dynamic SR custom workflow: {issue_type}...")
            from workflows.asset_service_request_handler import AssetServiceRequestHandler
            handler = AssetServiceRequestHandler()
            
            # Extract answers using conversation history
            extracted_answers = await handler.extract_asset_details_from_history(messages, clarification_answers)
            
            # Update state answers
            clarification_answers.update(extracted_answers)
            
            # Find next unanswered field
            next_field = handler.get_next_unanswered_field(clarification_answers)
            
            if next_field:
                logger.info(f"Asset SR missing field: {next_field['name']}")
                return {
                    "skill": skill,
                    "issue_type": issue_type,
                    "confidence": match_conf,
                    "clarification_needed": True,
                    "clarification_questions": [next_field["question"]],
                    "clarification_answers": clarification_answers,
                    "resolution": next_field["question"],
                    "routing_history": routing_history
                }
            else:
                logger.info("All Asset Service Request fields gathered successfully. Submitting to Freshservice...")
                sub_res = await handler.submit_to_freshservice("employee@elixir.portal", clarification_answers)
                
                if sub_res.get("success"):
                    ticket_id = sub_res["ticket_id"]
                    subject = sub_res["subject"]
                    
                    resolution_msg = f"""I have automatically raised a Freshservice **Service Request** ticket for you.

**Ticket Reference:** #{ticket_id}
**Subject:** {subject}
**Assignment Group:** IT Support Desk
**Status:** Open / Dispatched

Our support team has been notified and will review your request immediately."""
                    
                    return {
                        "skill": skill,
                        "issue_type": issue_type,
                        "confidence": match_conf,
                        "clarification_needed": False,
                        "clarification_answers": clarification_answers,
                        "resolution": resolution_msg,
                        "ticket_created": True,
                        "ticket_id": ticket_id,
                        "ticket_type": "Service Request",
                        "resolved": True,
                        "routing_history": routing_history
                    }
                else:
                    err_msg = sub_res.get("error", "Unknown error")
                    logger.error(f"Failed to submit Freshservice Service Request: {err_msg}")
                    return {
                        "skill": skill,
                        "issue_type": issue_type,
                        "confidence": match_conf,
                        "clarification_needed": False,
                        "resolved": True,  # Halt graph and present the error directly
                        "resolution": f"I gathered all the required details for the Service Request, but encountered an error submitting it to Freshservice:\n\n`{err_msg}`\n\nPlease try again or contact support.",
                        "routing_history": routing_history
                    }

        # Step 3: Extract clarification questions for the matched issue
        skill_details = self.kb_engine.get_skill_details(skill)
        if not skill_details:
            logger.info(f"No clarification questions needed for unknown or overridden skill: {skill}")
            return {
                "skill": skill,
                "issue_type": issue_type,
                "confidence": match_conf,
                "clarification_needed": False,
                "routing_history": routing_history
            }
            
        issue_details = skill_details.get("issues", {}).get(issue_type, {})
        if not issue_details:
            logger.info(f"No clarification questions needed for unknown issue: {issue_type}")
            return {
                "skill": skill,
                "issue_type": issue_type,
                "confidence": match_conf,
                "clarification_needed": False,
                "routing_history": routing_history
            }

        questions = issue_details.get("clarification_questions", [])

        if not questions:
            # No clarification questions needed for this issue (e.g. standard FAQs)
            logger.info(f"No clarification questions needed for {skill}/{issue_type}")
            return {
                "skill": skill,
                "issue_type": issue_type,
                "confidence": match_conf,
                "clarification_needed": False,
                "routing_history": routing_history
            }

        # Step 3: Check which questions have already been answered
        unanswered_questions = []

        for q in questions:
            # Special handling for account unlock SR name: if the user already mentions the target system (e.g. SAP MDG) in the query,
            # consider the *system* question answered. This should only apply to the first clarification question that asks about the system.
            if issue_type == "account_unlock_service_request" and q.lower().startswith("which system"):
                unlock_terms = ["sap mdg", "mdg", "sap ewm", "ewm", "sap prd", "prd"]
                if any(term in query.lower() for term in unlock_terms):
                    clarification_answers[q] = "Derived from user query"
                    continue


            # Check if this question is answered in the conversation history
            is_answered = await self._is_question_answered(q, query, full_conversation)
            if not is_answered:
                unanswered_questions.append(q)
            else:
                # Store answer as gathered (can do semantic slot filling if needed)
                clarification_answers[q] = "Gathered from context"

        if unanswered_questions:
            # We still need details. Ask the first unanswered question!
            next_q = unanswered_questions[0]
            
            # Context-aware question customization for hardware_issues to prevent "stupid questions"
            if "device is having the issue (Laptop, Desktop, or Screen/Monitor)" in next_q:
                query_lower = query.lower()
                if "mouse" in query_lower:
                    next_q = "Are you using this mouse with a Laptop or a Desktop?"
                elif "keyboard" in query_lower:
                    next_q = "Are you using this keyboard with a Laptop or a Desktop?"
                elif "screen" in query_lower or "monitor" in query_lower or "display" in query_lower:
                    next_q = "Is this an external Screen/Monitor, or is it the screen of a Laptop?"
            
            # Dynamic customization for SAP MDG questions
            if issue_type == "sap_mdg_issues":
                full_conv_lower = full_conversation.lower()
                mdg_subcat = None
                subcat_patterns = {
                    "Customer": ["customer"],
                    "Employee": ["employee"],
                    "Material": ["material"],
                    "Vendor Master Bulk update/Create": ["vendor master bulk", "vendor bulk"],
                    "Vendor Master non bulk update/Create": ["vendor master non", "vendor non-bulk", "vendor master non-bulk"],
                    "System Issues": ["system issue", "system down", "sap mdg system"],
                    "MDG PO integration": ["po integration", "purchase order integration"],
                    "MDG new integration/RFC/Service": ["new integration", "rfc", "rfc connection", "service integration"],
                    "MDG Master data download requests": ["master data download", "download request"],
                    "MDG Sync issue Debugging": ["sync issue", "synchronization issue", "sync debugging"],
                    "Common to all masters": ["common", "all masters"]
                }
                for sub, patterns in subcat_patterns.items():
                    if any(p in full_conv_lower for p in patterns):
                        mdg_subcat = sub
                        break
                if not mdg_subcat and "vendor" in full_conv_lower:
                    mdg_subcat = "Vendor Master non bulk update/Create"

                if "specific code" in next_q.lower() or "customer code, material code" in next_q.lower():
                    if mdg_subcat == "Customer":
                        next_q = "What is the specific Customer Code you are working with? (If not applicable, say NA)"
                    elif mdg_subcat == "Material":
                        next_q = "What is the specific Material Code you are working with? (If not applicable, say NA)"
                    elif mdg_subcat == "Employee":
                        next_q = "What is the specific Employee Code you are working with? (If not applicable, say NA)"
                    elif mdg_subcat and "Vendor" in mdg_subcat:
                        next_q = "What is the specific Vendor Code you are working with? (If not applicable, say NA)"
                    else:
                        next_q = "What is the specific code (Customer Code, Material Code, Vendor Code, or Employee Code) you are working with? (If not applicable, say NA)"

                elif "specific error or issue you are experiencing" in next_q.lower():
                    # Query actual database categories to pull matching items list
                    items = []
                    try:
                        from database.session import SessionLocal
                        from database.models import OperationalDomain
                        db = SessionLocal()
                        incident_domain = db.query(OperationalDomain).filter(OperationalDomain.domain_name == "incident_management").first()
                        if incident_domain and incident_domain.categories:
                            mdg_tree = incident_domain.categories.get("SAP MDG", {})
                            if mdg_subcat and mdg_subcat in mdg_tree:
                                items = mdg_tree[mdg_subcat]
                        db.close()
                    except Exception as e:
                        logger.error(f"Error fetching MDG subcategory items from database: {e}")
                        items = []

                    if mdg_subcat and items:
                        # Construct tailored suggestion of items
                        examples = []
                        for it in items:
                            clean_it = it.split(",")[0].split("(")[0].strip()
                            if clean_it and clean_it not in examples:
                                examples.append(clean_it)
                        examples_str = ", ".join(examples[:4])
                        if examples_str:
                            next_q = f"Could you please describe the specific error or issue you are experiencing? (e.g. {examples_str})"
                        else:
                            next_q = "Could you please describe the specific error or issue you are experiencing (e.g. data not reflecting in PRD, workflow error, block/unblock issue)?"
                    else:
                        if mdg_subcat == "Customer":
                            next_q = "Could you please describe the specific error or issue you are experiencing? (e.g. Sold-to-party not reflecting in PRD, GST / Credit limit changes, Address / Name change, etc.)"
                        elif mdg_subcat == "Material":
                            next_q = "Could you please describe the specific error or issue you are experiencing? (e.g. Material not available in PRD, block/unblock workflow, Shelf life or Warehouse extension issues)"
                        elif mdg_subcat == "Employee":
                            next_q = "Could you please describe the specific error or issue you are experiencing? (e.g. Employee code extension, Employee email-id changes, or Employee locked in other CR)"
                        elif mdg_subcat and "Vendor" in mdg_subcat:
                            next_q = "Could you please describe the specific error or issue you are experiencing? (e.g. Vendor Master bulk/non-bulk update or creation)"
                        else:
                            next_q = "Could you please describe the specific error or issue you are experiencing (e.g. data not reflecting in PRD, workflow error, block/unblock issue)?"
                    
            logger.info(f"Clarification needed. Asking: {next_q}")
            
            return {
                "skill": skill,
                "issue_type": issue_type,
                "confidence": match_conf,
                "clarification_needed": True,
                "clarification_questions": unanswered_questions,
                "clarification_answers": clarification_answers,
                "resolution": next_q,
                "routing_history": routing_history
            }
        
        # All questions answered! Proceed to Intent and routing
        logger.info("All clarification questions gathered successfully.")
        return {
            "skill": skill,
            "issue_type": issue_type,
            "confidence": match_conf,
            "clarification_needed": False,
            "clarification_answers": clarification_answers,
            "routing_history": routing_history
        }

    async def _is_question_answered(self, question: str, last_message: str, history: str) -> bool:
        """Uses a hybrid keyword-matching + LLM approach to check if a specific clarifying question is already answered."""
        q_lower = question.lower()
        m_lower = last_message.lower()
        hist_lower = history.lower()
        combined = f"{hist_lower}\n{m_lower}"

        # 1. Connection type question
        if "wi-fi" in q_lower or "ethernet" in q_lower or "external internet" in q_lower:
            keywords = ["wi-fi", "wifi", "ethernet", "external", "internet", "cable", "lan", "home", "wireless"]
            return any(kw in combined for kw in keywords)
            
        # 2. VPN error code question
        if "vpn error code" in q_lower or "gateway timeout" in q_lower or "auth failure" in q_lower:
            keywords = ["code", "timeout", "auth", "gateway", "error code", "error message"]
            return any(kw in combined for kw in keywords)
            
        # 3. Multiple users or location question
        if "multiple users" in q_lower or "location" in q_lower:
            keywords = ["multiple", "users", "everyone", "people", "location", "site", "office", "alone", "only me", "other"]
            return any(kw in combined for kw in keywords)
            
        # 4. Software name question
        if "name of the software" in q_lower or "salesforce" in q_lower or "adobe" in q_lower:
            keywords = ["salesforce", "adobe", "software", "license", "access", "office", "jira", "sap", "slack", "zoom", "teams"]
            return any(kw in combined for kw in keywords)
            
        # 5. Manager pre-approval question
        if "manager's written pre-approval" in q_lower or "approval" in q_lower:
            keywords = ["yes", "no", "approved", "approval", "manager", "pre-approval", "written"]
            return any(kw in combined for kw in keywords)
            
        # 6. Cost center code question
        if "cost center code" in q_lower:
            import re
            return bool(re.search(r'\d+', combined)) or "code" in combined
            
        # 7. Device category question
        if "device category" in q_lower or "laptop, monitor, mobile" in q_lower:
            keywords = ["laptop", "desktop", "monitor", "mobile", "phone", "tablet", "device"]
            return any(kw in combined for kw in keywords)
            
        # 8. New joiner or upgrade question
        if "new joiner or a device upgrade" in q_lower:
            keywords = ["joiner", "joinee", "new", "upgrade", "replacement", "replace"]
            return any(kw in combined for kw in keywords)

        # 9. Delivery address question
        if "delivery address" in q_lower or "office location" in q_lower:
            keywords = ["address", "location", "office", "street", "home", "ship", "delivery"]
            return any(kw in combined for kw in keywords)

        # 10. Database restore/PITR details question
        if "database instance id" in q_lower:
            keywords = ["db", "database", "instance", "schema", "name"]
            return any(kw in combined for kw in keywords)
        if "point-in-time recovery" in q_lower or "precise timestamp" in q_lower:
            keywords = ["timestamp", "time", "backup", "point-in-time", "date"]
            return any(kw in combined for kw in keywords)
        if "active production" in q_lower:
            keywords = ["prod", "production", "active", "yes", "no"]
            return any(kw in combined for kw in keywords)

        # 11. Device having the issue
        # 11. Device having the issue
        if "device is having the issue" in q_lower or "laptop, desktop, or screen" in q_lower:
            keywords = ["laptop", "desktop", "screen", "monitor", "pc", "computer", "display"]
            return any(kw in combined for kw in keywords)

        # 12. Symptom description
        if "describe the specific symptom" in q_lower:
            keywords = ["working", "button", "stuck", "unresponsive", "click", "crash", "hang", "boot", "flicker", "broken", "issue", "fail", "jam", "print", "scan", "error"]
            return any(kw in combined for kw in keywords)

        # 13. Asset tag or serial number
        if "asset tag or serial number" in q_lower:
            import re
            refusals = {"no", "none", "not available", "na", "don't have", "dont have", "unknown"}
            tokens = set(re.findall(r"[a-z']+", combined.lower()))
            has_refusal = bool(tokens.intersection(refusals))
            has_serial = bool(re.search(r'\d+', combined)) or "-" in combined
            return has_refusal or has_serial

        # 14. Printer/scanner type check
        if "printer issue, scanner issue, or a configuration" in q_lower:
            keywords = ["printer", "scanner", "jam", "print", "scan", "configuration", "error", "reconfig"]
            return any(kw in combined for kw in keywords)

        # 15. Printer/scanner location
        if "printer or scanner model/location" in q_lower:
            keywords = ["location", "model", "office", "desk", "room", "floor", "bay", "printer", "scanner"]
            return any(kw in combined for kw in keywords)

        # 16. Printer/scanner error code
        if "error code or message displayed" in q_lower:
            import re
            refusals = {"no", "none", "not available", "na", "dont know", "no error"}
            tokens = set(re.findall(r"[a-z']+", combined.lower()))
            has_refusal = bool(tokens.intersection(refusals))
            has_error = "error" in combined or "code" in combined or bool(re.search(r'\d+', combined))
            return has_refusal or has_error

        # 17. SAP MDG - Master Data Area
        if "master data area" in q_lower or "common to all masters, customer" in q_lower:
            keywords = ["common", "customer", "employee", "material", "system", "vendor"]
            import re
            return any(re.search(rf"\b{kw}\b", combined.lower()) for kw in keywords)

        # 18. SAP MDG - Specific Code
        if "specific code" in q_lower or "customer code, material code" in q_lower:
            allowed_questions = ["specific code", "customer code", "material code", "vendor code", "employee code"]
            if not any(aq in history.lower() for aq in allowed_questions):
                return False
            import re
            refusals = {"no", "none", "not available", "na", "dont know", "no code", "skip"}
            tokens = set(re.findall(r"[a-z']+", combined.lower()))
            has_refusal = bool(tokens.intersection(refusals))
            has_code = bool(re.search(r'\d+', combined)) or "-" in combined or "code" in combined
            return has_refusal or has_code

        # 19. SAP MDG - Specific Error
        if "specific error or issue you are experiencing" in q_lower:
            if "describe the specific error" not in history.lower() and "specific error or issue" not in history.lower():
                return False
            return True

        # 20. SAP MDG - Change Request (CR) ID
        if "mdg change request" in q_lower or "cr id" in q_lower:
            if "change request (cr)" not in history.lower() and "cr id" not in history.lower():
                return False
            import re
            refusals = {"no", "none", "not available", "na", "dont know", "no id", "skip"}
            tokens = set(re.findall(r"[a-z']+", combined.lower()))
            has_refusal = bool(tokens.intersection(refusals))
            has_id = bool(re.search(r'\d+', combined)) or "cr" in combined or "request" in combined
            return has_refusal or has_id

        # Fallback to direct, strict QA classification prompt
        prompt = f"""Text: "{last_message}"
Question: "{question}"
Does the Text contain the specific answer to the Question? (yes/no):"""
        try:
            response = await self.llm.generate_response(prompt, system_prompt="You are a strict QA assistant.")
            logger.info(f"Question checker LLM Response for '{question}': '{response.strip()}'")
            clean_res = response.strip().upper().replace(".", "").replace(",", "").replace("'", "").replace('"', '').split()
            if not clean_res:
                return False
            return clean_res[0] == "YES"
        except Exception as e:
            logger.error(f"Error checking if question was answered: {str(e)}")
            return False
