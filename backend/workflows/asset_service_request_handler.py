import base64
import json
import os
import requests
from typing import Dict, Any, List, Optional
from loguru import logger
from integrations.ollama_service import OllamaService
from config.settings import settings

ASSET_SR_CATEGORIES = {}

class AssetServiceRequestHandler:
    def __init__(self):
        self.llm = OllamaService()
        self.domain = settings.FRESHSERVICE_DOMAIN
        self.api_key = settings.FRESHSERVICE_API_KEY
        self.display_id = 26

    def _load_categories(self) -> Dict[str, Any]:
        """Loads categories JSON from DB for service_request_management."""
        from database.session import SessionLocal
        from database.models import OperationalDomain
        
        db = SessionLocal()
        try:
            domain = db.query(OperationalDomain).filter(OperationalDomain.domain_name == "service_request_management").first()
            if domain and domain.categories:
                cats = domain.categories
                if isinstance(cats, str):
                    return json.loads(cats)
                return cats
        except Exception as e:
            logger.error(f"Failed to load Service Request categories from database: {e}")
        finally:
            db.close()
        return {}

    def _get_sr_choices_and_mapping(self, categories: Dict[str, Any]):
        """Returns a list of all choices and a map from choice to (catalog_item_name, display_id, fields_list)."""
        all_choices = []
        mapping = {}
        for cat_name, cat_data in categories.items():
            display_id = cat_data.get("display_id", 26)
            sr_field = cat_data.get("fields", {}).get("sr_name", {})
            choices = sr_field.get("choices", [])
            dynamic_sections = cat_data.get("dynamic_sections", {})
            
            # Extract root-level base fields (excluding sr_name and untitled)
            root_fields = cat_data.get("fields", {})
            base_fields_list = []
            for f_name, f_info in root_fields.items():
                if f_name not in ["sr_name", "untitled"]:
                    base_fields_list.append({
                        "name": f_name,
                        "label": f_info.get("label"),
                        "type": f_info.get("type"),
                        "required": f_info.get("required", False),
                        "question": f_info.get("question")
                    })
            
            if choices:
                for choice in choices:
                    all_choices.append(choice)
                    dynamic_fields = dynamic_sections.get(choice, [])
                    # Merge base fields with dynamic section fields
                    fields = base_fields_list + dynamic_fields
                    mapping[choice] = {
                        "catalog_name": cat_name,
                        "display_id": display_id,
                        "fields": fields
                    }
            else:
                # If there are no choices (it's Account Unlock or Password reset)
                if cat_name in ["Account Unlock", "Password reset"]:
                    # Dynamically generate flattened choices
                    sys_field_name = "account_unlock_for" if cat_name == "Account Unlock" else "password_reset_for"
                    whom_field_name = "for_whom_to_unlock" if cat_name == "Account Unlock" else "for_whom_to_reset"
                    
                    sys_choices = root_fields.get(sys_field_name, {}).get("choices", [])
                    whom_choices = root_fields.get(whom_field_name, {}).get("choices", [])
                    
                    for sys_c in sys_choices:
                        for whom_c in whom_choices:
                            whom_c_clean = "Common ID" if "Common ID" in whom_c else whom_c
                            choice_name = f"{cat_name} for {sys_c} ({whom_c_clean})"
                            all_choices.append(choice_name)
                            
                            sys_fields = dynamic_sections.get(sys_c, [])
                            whom_fields = dynamic_sections.get(whom_c, [])
                            if not whom_fields and whom_c != whom_c_clean:
                                whom_fields = dynamic_sections.get(whom_c_clean, [])
                                
                            fields = base_fields_list + sys_fields + whom_fields
                            mapping[choice_name] = {
                                "catalog_name": cat_name,
                                "display_id": display_id,
                                "fields": fields
                            }
                else:
                    all_choices.append(cat_name)
                    mapping[cat_name] = {
                        "catalog_name": cat_name,
                        "display_id": display_id,
                        "fields": base_fields_list
                    }
        return all_choices, mapping

    def _prepopulate_slots_from_sr_choice(self, sr_name: str, updated: Dict[str, str]):
        if not sr_name:
            return
        sr_name_lower = sr_name.lower()
        
        # Account Unlock / Password Reset system mapping
        if "sap mdg" in sr_name_lower:
            updated["account_unlock_for"] = "SAP MDG"
            updated["password_reset_for"] = "SAP MDG"
        elif "sap prd" in sr_name_lower:
            updated["account_unlock_for"] = "SAP PRD"
            updated["password_reset_for"] = "SAP PRD"
        elif "sap ewm" in sr_name_lower:
            updated["account_unlock_for"] = "SAP EWM"
            updated["password_reset_for"] = "SAP EWM"
        elif "sap tm" in sr_name_lower or "tlb" in sr_name_lower:
            updated["password_reset_for"] = "SAP TM/TLB"
            
        # Target recipient mapping
        if "(self)" in sr_name_lower:
            updated["for_whom_to_unlock"] = "Self"
            updated["for_whom_to_reset"] = "Self"
        elif "(common id)" in sr_name_lower:
            updated["for_whom_to_unlock"] = "Common ID's"
            updated["for_whom_to_reset"] = "Common ID's"
            updated["whom_to_reset_for"] = "Common ID"
            updated["reset_for_whom"] = "Common ID"
        elif "(someone else)" in sr_name_lower:
            updated["for_whom_to_unlock"] = "Someone else"
            updated["for_whom_to_reset"] = "Someone else"

    def _match_sr_name_by_keywords(self, query: str, choices: List[str]) -> Optional[str]:
        q = query.lower()
        
        # Direct substring match first
        for choice in choices:
            if choice.lower() in q:
                return choice
                
        # Heuristic mapping
        heuristics = {
            "Laptop Request for New Joinee": ["new joinee", "new hire", "onboard", "joinee laptop", "joiner laptop", "new joiner", "joiner"],
            "Laptop Request in cases of Transfer / Promotion": ["transfer laptop", "promotion laptop", "transfer/promotion"],
            "Request for allocation of Temporary / Project / Team laptop/Desktop": ["temporary laptop", "project laptop", "team laptop", "temp laptop"],
            "Request for replacement of Desktop/Laptop/Tab": ["replacement", "replace laptop", "replace desktop", "replace tab", "replace monitor"],
            "Surrender of Laptop": ["surrender", "return laptop", "give back"],
            "Self certified assets": ["self cert", "certify asset", "certification"],
            "Request for laptop allocation (Offrole Only)": ["offrole", "off-role", "off role"],
            "New Service Request in Fixed Assets": ["new service request in fixed assets", "fixed asset request"],
            "Initiate Asset Transfer": ["asset transfer", "transfer asset", "transfer of asset", "transfer an asset"],
            "Dispose an asset": ["dispose", "disposal", "scrap asset"],
            "Create new login for Fixed Assets (NGP ID)": ["create login", "ngp id", "fixed assets login"],
            "Ad-hoc request": ["ad-hoc", "adhoc", "ad hoc"],
            "Additional Requirement/Device Upgradation": ["device upgradation", "upgradation", "device upgrade", "upgrade device", "additional requirement", "hardware upgrade", "ram", "hdd", "charger", "adaptor", "connector", "connectors"],
            
            # Account Unlock / Password Reset triggers
            "Account Unlock for SAP MDG (Self)": ["unlock mdg self", "unlock sap mdg self", "unlock mdg"],
            "Account Unlock for SAP MDG (Common ID)": ["unlock mdg common", "unlock sap mdg common"],
            "Account Unlock for SAP MDG (Someone else)": ["unlock mdg someone else", "unlock mdg for someone else"],
            "Account Unlock for SAP PRD (Self)": ["unlock prd self", "unlock sap prd self", "unlock prd"],
            "Account Unlock for SAP PRD (Common ID)": ["unlock prd common", "unlock sap prd common"],
            "Account Unlock for SAP PRD (Someone else)": ["unlock prd someone else", "unlock prd for someone else"],
            "Account Unlock for SAP EWM (Self)": ["unlock ewm self", "unlock sap ewm self", "unlock ewm"],
            "Account Unlock for SAP EWM (Common ID)": ["unlock ewm common", "unlock sap ewm common", "unlock ewm common id"],
            "Account Unlock for SAP EWM (Someone else)": ["unlock ewm someone else", "unlock ewm for someone else"],
            
            "Password reset for SAP MDG (Self)": ["reset mdg self", "reset password mdg self", "reset mdg password", "password reset mdg"],
            "Password reset for SAP MDG (Common ID)": ["reset mdg common", "reset password mdg common", "mdg password common"],
            "Password reset for SAP MDG (Someone else)": ["reset mdg someone else", "reset password mdg someone else"],
            "Password reset for SAP PRD (Self)": ["reset prd self", "reset password prd self", "reset prd password", "password reset prd", "prd password reset"],
            "Password reset for SAP PRD (Common ID)": ["reset prd common", "reset password prd common", "prd password common"],
            "Password reset for SAP PRD (Someone else)": ["reset prd someone else", "reset password prd someone else"],
            "Password reset for SAP EWM (Self)": ["reset ewm self", "reset password ewm self", "reset ewm password", "password reset ewm"],
            "Password reset for SAP EWM (Common ID)": ["reset ewm common", "reset password ewm common", "ewm password common"],
            "Password reset for SAP EWM (Someone else)": ["reset ewm someone else", "reset password ewm someone else"],
            "Password reset for SAP TM/TLB (Self)": ["reset tm self", "reset password tm self", "reset tm password", "password reset tm", "reset tlb", "password reset tlb"],
            "Password reset for SAP TM/TLB (Common ID)": ["reset tm common", "reset password tm common", "tm password common"],
            "Password reset for SAP TM/TLB (Someone else)": ["reset tm someone else", "reset password tm someone else"]
        }
        
        for choice, patterns in heuristics.items():
            if choice in choices:
                for pattern in patterns:
                    if pattern in q:
                        return choice
        return None

    def resolve_location_id(self, val: str) -> Optional[int]:
        """Resolves a location name or ID string to a valid integer location ID using a cached local database/JSON."""
        if not val:
            return None
        val_clean = val.strip()
        if val_clean.isdigit():
            return int(val_clean)
            
        # Try loading from local cache file
        cache_path = os.path.join(os.path.dirname(__file__), "locations_cache.json")
        locs = []
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    locs = json.load(f)
            except Exception as e:
                logger.error(f"Error reading locations cache: {e}")
                
        # If cache is empty, fetch all locations from Freshservice and save them
        if not locs:
            logger.info("Locations cache empty. Fetching all locations from Freshservice...")
            try:
                auth_str = f"{self.api_key}:X"
                b64_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
                headers = {
                    "Authorization": f"Basic {b64_auth}"
                }
                page = 1
                while True:
                    url = f"https://{self.domain}/api/v2/locations?per_page=100&page={page}"
                    response = requests.get(url, headers=headers, timeout=20.0)
                    if response.status_code == 200:
                        data = response.json().get("locations", [])
                        locs.extend(data)
                        if len(data) < 100:
                            break
                        page += 1
                    else:
                        break
                        
                if locs:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(locs, f, indent=2)
                    logger.info(f"Successfully cached {len(locs)} locations.")
            except Exception as e:
                logger.error(f"Failed to fetch and cache locations: {e}")
                
        # Search for matches
        val_lower = val_clean.lower()
        
        # 1. Look for exact matches
        for loc in locs:
            if loc["name"].lower() == val_lower:
                return loc["id"]
                
        # 2. Look for case-insensitive partial match
        for loc in locs:
            if val_lower in loc["name"].lower() or loc["name"].lower() in val_lower:
                return loc["id"]
                
        return None

    def get_next_scoping_question(self, answers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Returns the next needs-understanding question that must be answered before suggesting an SR."""
        if not answers.get("scoping_purpose"):
            return {
                "name": "scoping_purpose",
                "question": "To help you with this asset request, could you please tell me if this is for a new hire onboarding, a device upgrade/replacement, a transfer, or a temporary project?"
            }
        if not answers.get("scoping_device_type"):
            return {
                "name": "scoping_device_type",
                "question": "What type of device is required (e.g. Windows Laptop, MacBook, Desktop, or Tablet)?"
            }
        if not answers.get("scoping_special_software"):
            return {
                "name": "scoping_special_software",
                "question": "Does this user need any specialized software pre-installed, or do they have any high-performance hardware requirements?"
            }
        return None

    async def extract_asset_details_from_history(self, messages: List[Dict[str, Any]], current_answers: Dict[str, str]) -> Dict[str, str]:
        updated = {**current_answers}
        if not messages: return updated
        latest_msg = messages[-1]["content"].lower()
        # Load categories and compute available SR choices
        categories = self._load_categories()
        all_choices, mapping = self._get_sr_choices_and_mapping(categories)
        # Detect unlock/reset intent and extract system and recipient
        # Determine intent type for SR name generation
        if "unlock" in latest_msg:
            parts = ["Account Unlock"]
        elif "reset" in latest_msg:
            parts = ["Password reset"]
        else:
            parts = []
        sys = next((x for x in ["SAP MDG", "SAP PRD", "SAP EWM", "SAP TM"] if x.lower() in latest_msg), "")
        whom = next((x for x in ["Self", "Common ID", "Someone else"] if x.lower() in latest_msg), "")
        # Store identified system for later prompts
        if sys:
            updated["account_unlock_for"] = sys
        # If unlock/reset intent detected but SR name not set yet, ask for permission to raise SR
        if (parts and sys) and not updated.get("sr_name"):
            # This will trigger a permission question in get_next_unanswered_field
            updated["awaiting_permission"] = True
        # If no categories loaded, fallback to heuristics for unlock/password reset
        matched = None
        if not all_choices:
            # Only attempt fallback matching if we have a recipient identified
            if whom:
                fallback_choices = [
                    "Account Unlock for SAP MDG (Self)",
                    "Account Unlock for SAP MDG (Common ID)",
                    "Account Unlock for SAP MDG (Someone else)",
                    "Account Unlock for SAP PRD (Self)",
                    "Account Unlock for SAP PRD (Common ID)",
                    "Account Unlock for SAP PRD (Someone else)",
                    "Account Unlock for SAP EWM (Self)",
                    "Account Unlock for SAP EWM (Common ID)",
                    "Account Unlock for SAP EWM (Someone else)",
                    "Password reset for SAP MDG (Self)",
                    "Password reset for SAP MDG (Common ID)",
                    "Password reset for SAP MDG (Someone else)",
                    "Password reset for SAP PRD (Self)",
                    "Password reset for SAP PRD (Common ID)",
                    "Password reset for SAP PRD (Someone else)",
                    "Password reset for SAP EWM (Self)",
                    "Password reset for SAP EWM (Common ID)",
                    "Password reset for SAP EWM (Someone else)"
                ]
                matched = self._match_sr_name_by_keywords(latest_msg, fallback_choices)
        else:
            matched = self._match_sr_name_by_keywords(latest_msg, all_choices)


        if matched: updated["sr_name"] = matched
        if updated.get("sr_name"): self._prepopulate_slots_from_sr_choice(updated["sr_name"], updated)
        return updated

    def get_next_unanswered_field(self, answers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Returns the next field that needs to be collected, along with its friendly question."""
        categories = self._load_categories()
        all_choices, mapping = self._get_sr_choices_and_mapping(categories)
        sr_name = answers.get("sr_name")
        if sr_name and (sr_name.startswith("Account Unlock") or sr_name.startswith("Password reset")):
             for field in mapping[sr_name]["fields"]:
                 if not answers.get(field["name"]): return field
        # If we flagged that permission is needed, ask for it first
        if answers.get("awaiting_permission"):
            return {
                "name": "permission",
                "question": "I understand you want to unlock an account. May I raise a Service Request on your behalf?"
            }
        if not answers.get("sr_name"):
            scoping_q = self.get_next_scoping_question(answers)
            if scoping_q: return scoping_q
        if not sr_name:
            return {
                "name": "sr_name",
                "label": "SR Name",
                "type": "custom_dropdown",
                "question": "What type of Asset Request would you like to raise? Please select one of the following:\n\n" + \
                             "\n".join([f"• *{c}*" for c in all_choices])
            }
        if sr_name not in mapping: return None
        fields = mapping[sr_name]["fields"]
        for f in fields:
            if not answers.get(f["name"]):
                return f
        return None

    async def submit_to_freshservice(self, requester_email: str, answers: Dict[str, str]) -> Dict[str, Any]:
        """Submits the gathered details to the Freshservice Service Item catalog place request API."""
        categories = self._load_categories()
        _, mapping = self._get_sr_choices_and_mapping(categories)
        
        sr_name = answers.get("sr_name")
        if not sr_name or sr_name not in mapping:
            return {
                "success": False,
                "error": f"Invalid or missing Service Request choice: {sr_name}"
            }
            
        display_id = mapping[sr_name]["display_id"]
        fields = mapping[sr_name]["fields"]
        
        url = f"https://{self.domain}/api/v2/service_catalog/items/{display_id}/place_request"
        
        auth_str = f"{self.api_key}:X"
        b64_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {b64_auth}"
        }
        
        # Build the payload custom fields mapping all collected slots
        custom_fields_payload = {}
        
        catalog_item_data = categories.get(mapping[sr_name]["catalog_name"], {})
        base_fields = catalog_item_data.get("fields", {})
        if "sr_name" in base_fields:
            custom_fields_payload["sr_name"] = sr_name
        if "untitled" in base_fields:
            custom_fields_payload["untitled"] = f"Request for {sr_name} raised automatically by the Elixir Portal AI Service Desk."
            
        # EWM / SAP TM common ID helpers to copy ID to EWM common ID fields
        if mapping[sr_name]["catalog_name"] in ["Account Unlock", "Password reset"]:
            c_id = answers.get("common_id") or answers.get("common_id_s")
            if c_id:
                if "add_common_id" in [f["name"] for f in fields]:
                    custom_fields_payload["add_common_id"] = c_id
        
        for field in fields:
            val = answers.get(field["name"])
            if val:
                # Cast lookups/numbers if needed
                if field["type"] in ["custom_lookup_bigint", "custom_number"]:
                    if "location" in field["name"]:
                        resolved_id = self.resolve_location_id(val)
                        if resolved_id:
                            custom_fields_payload[field["name"]] = resolved_id
                        else:
                            logger.warning(f"Could not resolve location '{val}' for field '{field['name']}'. Omitted from payload.")
                    else:
                        try:
                            custom_fields_payload[field["name"]] = int(val)
                        except ValueError:
                            if val.strip().isdigit():
                                custom_fields_payload[field["name"]] = int(val)
                            else:
                                logger.warning(f"Invalid numeric value '{val}' for field '{field['name']}'. Omitted from payload.")
                else:
                    custom_fields_payload[field["name"]] = val

        payload = {
            "quantity": 1,
            "requested_for": requester_email,
            "email": requester_email,
            "custom_fields": custom_fields_payload
        }
        
        logger.info(f"Submitting Freshservice Service Request for {sr_name} to {url}...")
        try:
            # Run in executor to avoid blocking asyncio loop
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(url, headers=headers, json=payload, timeout=30.0)
            )
            
            logger.info(f"Freshservice Submit Response Code: {response.status_code}")
            if response.status_code in [200, 201]:
                res_data = response.json()
                sr_info = res_data.get("service_request", {})
                return {
                    "success": True,
                    "ticket_id": str(sr_info.get("id")),
                    "subject": sr_info.get("subject") or f"Service Request: {sr_name}",
                    "assignment_group": "IT Support Desk",
                    "status": "Open / Dispatched",
                    "raw_response": res_data
                }
            else:
                logger.error(f"Error submitting request: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": response.text
                }
        except Exception as e:
            logger.error(f"Failed to submit Service Request: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
