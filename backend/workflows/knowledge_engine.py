import os
import json
from typing import Dict, Any, Optional, Tuple, List
from loguru import logger

class KnowledgeEngine:
    def __init__(self, file_path: str = None):
        if file_path is None:
            # Default to the current directory of the module
            current_dir = os.path.dirname(os.path.abspath(__file__))
            file_path = os.path.join(current_dir, "knowledge_base.json")
        self.file_path = file_path
        self.data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                logger.error(f"Knowledge base file not found at {self.file_path}")
                return {}
        except Exception as e:
            logger.error(f"Error loading knowledge base: {str(e)}")
            return {}

    def get_skill_details(self, skill: str) -> Optional[Dict[str, Any]]:
        return self.data.get(skill)

    def match_workflow(self, query: str) -> Tuple[Optional[str], Optional[str], float]:
        """
        Determines the most appropriate skill and issue type based on user query.
        Uses exact keyword, title, description, and sub-issue matching.
        Returns:
            (skill, issue_type, confidence)
        """
        query_lower = query.lower()
        
        best_skill = None
        best_issue = None
        max_score = 0.0

        for skill_key, skill_val in self.data.items():
            # Check skill level keywords/description
            skill_score = 0.0
            if skill_key in query_lower:
                skill_score += 0.3
            if skill_val.get("displayName", "").lower() in query_lower:
                skill_score += 0.4
            
            # Check individual issues
            issues = skill_val.get("issues", {})
            for issue_key, issue_val in issues.items():
                issue_score = skill_score
                display_name = issue_val.get("displayName", "").lower()
                
                # Exact or substring match on issue key
                if issue_key.replace("_", " ") in query_lower or issue_key in query_lower:
                    issue_score += 0.5
                
                # Match display name
                if display_name in query_lower:
                    issue_score += 0.6
                
                # Check individual words for partial matching
                query_words = set(query_lower.split())
                display_words = set(display_name.split())
                common_words = query_words.intersection(display_words)
                if common_words:
                    # Filter out common stop words
                    stop_words = {"issue", "the", "a", "an", "and", "or", "to", "for", "with", "on", "not"}
                    meaningful_words = common_words - stop_words
                    if meaningful_words:
                        issue_score += 0.1 * len(meaningful_words)

                # Route-specific triggers for the 5 ITSM domains
                if skill_key == "sr_workflow":
                    if any(kw in query_lower for kw in ["sr", "service request", "provision", "hardware", "request", "onboard", "device", "upgrade", "ram", "memory", "unlock", "reset", "mdg", "password"]):
                        issue_score += 0.2
                    if any(kw in query_lower for kw in ["hardware", "device", "laptop", "monitor", "ram", "memory", "upgrade", "ssd", "disk"]):
                        if issue_key == "hardware_provisioning":
                            issue_score += 0.4
                    if issue_key == "asset_allocation_surrender":
                        asset_trigger_terms = [
                            "asset allocation",
                            "surrender",
                            "asset request",
                            "laptop request",
                            "desktop request",
                            "tablet request",
                            "tab request",
                            "new laptop",
                            "need laptop",
                            "need new laptop",
                            "request new laptop",
                            "laptop allocation",
                            "desktop allocation",
                            "new desktop",
                            "want laptop",
                            "want a laptop",
                            "need a laptop",
                            "request a laptop",
                            "get a laptop",
                            "get laptop",
                            "order laptop",
                            "order a laptop",
                            "request laptop",
                            "i want a laptop",
                            "want a computer",
                            "need a computer",
                            "self-certification",
                            "self certification",
                            "certification",
                            "certify",
                            "transfer",
                            "promotion",
                            "temporary",
                            "project",
                            "team",
                            "joinee",
                            "joiner",
                            "new joinee",
                            "replace",
                            "replacement",
                            "fixed asset",
                            "fixed assets",
                            "asset transfer",
                            "transfer asset",
                            "dispose asset",
                            "disposal",
                            "ngp id",
                            "dispose",
                            "ram",
                            "hdd",
                            "charger",
                            "adaptor",
                            "connector",
                            "connectors",
                            "hardware requirement",
                            "additional hardware",
                            "device upgradation",
                            "upgradation",
                            "upgrade ram",
                            "increase ram",
                            "upgrade my ram"
                        ]
                        if any(term in query_lower for term in asset_trigger_terms):
                            issue_score += 0.6
                        elif "asset" in query_lower:
                            # Only partial asset context, keep match low to avoid overmatching unrelated queries.
                            issue_score += 0.1
                    elif issue_key == "mdg_service_request":
                        mdg_sr_terms = ["bulk master", "bulk update", "user provisioning", "gst maintenance", "org element", "mdg request", "mdg sr", "mdg user", "mdg service"]
                        if any(term in query_lower for term in mdg_sr_terms):
                            issue_score += 0.8
                    elif issue_key == "account_unlock_service_request":
                        unlock_terms = ["unlock", "account unlock", "unlock my account", "unlocked", "unlock account"]
                        if any(term in query_lower for term in unlock_terms):
                            issue_score += 1.0
                    elif issue_key == "password_reset_service_request":
                        reset_terms = ["password reset", "reset my password", "forgot password", "reset password", "reset passcode", "password change", "change password"]
                        if any(term in query_lower for term in reset_terms):
                            issue_score += 0.8

                elif skill_key == "incident_workflow":
                    if any(kw in query_lower for kw in ["incident", "crash", "broken", "error", "failed", "not working", "hang", "boot", "mouse", "keyboard", "printer", "scanner", "screen", "monitor", "display", "jam", "mdg", "sap mdg", "change request", "master data", "cr id", "material code", "customer code", "vendor code", "employee code"]):
                        issue_score += 0.2
                    if any(kw in query_lower for kw in ["hardware", "desktop", "laptop", "mouse", "keyboard", "screen", "monitor", "display", "crash", "hang", "boot"]):
                        if issue_key == "hardware_issues":
                            issue_score += 0.4
                    if any(kw in query_lower for kw in ["printer", "scanner", "jam", "print", "scan"]):
                        if issue_key == "printer_scanner_issues":
                            issue_score += 0.4
                    if any(kw in query_lower for kw in ["mdg", "sap mdg", "change request", "master data", "cr id", "material code", "customer code", "vendor code", "employee code"]):
                        if issue_key == "sap_mdg_issues":
                            issue_score += 0.8

                if issue_score > max_score:
                    max_score = issue_score
                    best_skill = skill_key
                    best_issue = issue_key

        # Normalize score between 0.0 and 1.0 (heuristically)
        normalized_score = min(max_score / 1.5, 1.0)
        
        # If we have a very low score, default to none
        if normalized_score < 0.2:
            return None, None, 0.0
            
        return best_skill, best_issue, normalized_score
