import httpx
import base64
from typing import Dict, Any, List, Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import settings

class FreshserviceService:
    def __init__(self):
        self.domain = settings.FRESHSERVICE_DOMAIN
        self.api_key = settings.FRESHSERVICE_API_KEY
        self.base_url = f"https://{self.domain}/api/v2"
        
        # Base64 encode API key for Basic Auth
        auth_str = f"{self.api_key}:X"
        b64_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {b64_auth}"
        }
        self.timeout = httpx.Timeout(30.0)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def create_ticket(self, subject: str, description: str, email: str, priority: int = 2, status: int = 2, type: str = "Incident", category: Optional[str] = None, sub_category: Optional[str] = None, item_category: Optional[str] = None) -> Dict[str, Any]:
        """Create a new ticket in Freshservice."""
        logger.info(f"Creating Freshservice {type} ticket for {email}")
        
        payload = {
            "subject": subject,
            "description": description,
            "email": email,
            "priority": priority,
            "status": status,
            "type": type,
            "custom_fields": {
                "contact_number": 1234567890
            }
        }
        if category:
            payload["category"] = category
        if sub_category:
            payload["sub_category"] = sub_category
        if item_category:
            payload["item_category"] = item_category
            
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(f"{self.base_url}/tickets", headers=self.headers, json=payload)
                response.raise_for_status()
                return response.json().get("ticket", {})
            except Exception as e:
                logger.error(f"Error creating Freshservice ticket: {str(e)}")
                raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_ticket_status(self, ticket_id: str) -> Dict[str, Any]:
        """Get the status of an existing ticket."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(f"{self.base_url}/tickets/{ticket_id}", headers=self.headers)
                response.raise_for_status()
                return response.json().get("ticket", {})
            except Exception as e:
                logger.error(f"Error fetching Freshservice ticket {ticket_id}: {str(e)}")
                raise

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def add_note(self, ticket_id: str, body: str, private: bool = False) -> Dict[str, Any]:
        """Add a note to a ticket."""
        payload = {
            "body": body,
            "private": private
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(f"{self.base_url}/tickets/{ticket_id}/notes", headers=self.headers, json=payload)
                response.raise_for_status()
                return response.json().get("note", {})
            except Exception as e:
                logger.error(f"Error adding note to ticket {ticket_id}: {str(e)}")
                raise
