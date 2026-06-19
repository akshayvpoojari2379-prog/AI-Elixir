import asyncio
import os
import sys
import uuid
from loguru import logger

# Add backend directory to path
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

# Set environment placeholders to allow importing without DB/Ollama connections crashing
os.environ["DATABASE_URL"] = "postgresql://postgres:*sleek#@localhost:5432/ai_service_desk"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["FRESHSERVICE_DOMAIN"] = "mock.freshservice.com"
os.environ["FRESHSERVICE_API_KEY"] = "mock_key"
os.environ["JWT_SECRET"] = "mock_secret"

from workflows.orchestrator import process_service_desk_query

async def run_diagnostic():
    session_id = str(uuid.uuid4())
    from unittest.mock import patch, MagicMock
    
    mock_resp = MagicMock()
    mock_resp.status_code = 201
    mock_resp.json.return_value = {
        "service_request": {
            "id": 12345,
            "subject": "Laptop Request for New Joinee"
        }
    }
    
    with patch("requests.post", return_value=mock_resp):
        logger.info("--- TURN 1: Requesting Laptop for New Joinee ---")
        try:
            res1 = await process_service_desk_query(session_id, "I want to request a laptop for a new joinee")
            logger.info(f"Turn 1 Response: {res1.get('response')}")
        except Exception as e:
            logger.exception("Turn 1 failed with exception:")
    
        logger.info("--- TURN 2: Providing Device Type ---")
        try:
            res2 = await process_service_desk_query(session_id, "Windows Laptop")
            logger.info(f"Turn 2 Response: {res2.get('response')}")
        except Exception as e:
            logger.exception("Turn 2 failed with exception:")
    
        logger.info("--- TURN 3: Providing Special Software / Hardware Needs ---")
        try:
            res3 = await process_service_desk_query(session_id, "No special software or high-performance hardware needed, standard office setup is fine")
            logger.info(f"Turn 3 Response: {res3.get('response')}")
        except Exception as e:
            logger.exception("Turn 3 failed with exception:")

        logger.info("--- TURN 4: Providing Date of Joining ---")
        try:
            res4 = await process_service_desk_query(session_id, "2026-06-15")
            logger.info(f"Turn 4 Response: {res4.get('response')}")
        except Exception as e:
            logger.exception("Turn 4 failed with exception:")

        logger.info("--- TURN 5: Providing Name of New Joinee ---")
        try:
            res5 = await process_service_desk_query(session_id, "Jane Doe")
            logger.info(f"Turn 5 Response: {res5.get('response')}")
        except Exception as e:
            logger.exception("Turn 5 failed with exception:")

        logger.info("--- TURN 6: Providing employee Code ---")
        try:
            res6 = await process_service_desk_query(session_id, "E00998877")
            logger.info(f"Turn 6 Response: {res6.get('response')}")
        except Exception as e:
            logger.exception("Turn 6 failed with exception:")

        logger.info("--- TURN 7: Providing contact number ---")
        try:
            res7 = await process_service_desk_query(session_id, "9876543210")
            logger.info(f"Turn 7 Response: {res7.get('response')}")
        except Exception as e:
            logger.exception("Turn 7 failed with exception:")

        logger.info("--- TURN 8: Providing department ---")
        try:
            res8 = await process_service_desk_query(session_id, "Engineering")
            logger.info(f"Turn 8 Response: {res8.get('response')}")
        except Exception as e:
            logger.exception("Turn 8 failed with exception:")

        logger.info("--- TURN 9: Providing Location Name ---")
        try:
            res9 = await process_service_desk_query(session_id, "Mumbai Office")
            logger.info(f"Turn 9 Response: {res9.get('response')}")
        except Exception as e:
            logger.exception("Turn 9 failed with exception:")

        logger.info("--- TURN 10: Providing Joining Location ---")
        try:
            res10 = await process_service_desk_query(session_id, "290000001")
            logger.info(f"Turn 10 Response: {res10.get('response')}")
        except Exception as e:
            logger.exception("Turn 10 failed with exception:")

        logger.info("--- TURN 11: Providing Name of Admin ---")
        try:
            res11 = await process_service_desk_query(session_id, "Akshay Poojari")
            logger.info(f"Turn 11 Response: {res11.get('response')}")
        except Exception as e:
            logger.exception("Turn 11 failed with exception:")

        logger.info("--- TURN 12: Providing Contact Number of Admin ---")
        try:
            res12 = await process_service_desk_query(session_id, "9988776655")
            logger.info(f"Turn 12 Response: {res12.get('response')}")
        except Exception as e:
            logger.exception("Turn 12 failed with exception:")

        logger.info("--- TURN 13: Providing Address ---")
        try:
            res13 = await process_service_desk_query(session_id, "123 Tech Park, Mumbai")
            logger.info(f"Turn 13 Response: {res13.get('response')}")
        except Exception as e:
            logger.exception("Turn 13 failed with exception:")

        logger.info("--- TURN 14: Providing Designation ---")
        try:
            res14 = await process_service_desk_query(session_id, "Software Engineer")
            logger.info(f"Turn 14 Response: {res14.get('response')}")
        except Exception as e:
            logger.exception("Turn 14 failed with exception:")

        logger.info("--- TURN 15: Providing Details ---")
        try:
            res15 = await process_service_desk_query(session_id, "Standard corporate developer software suite required.")
            logger.info(f"Turn 15 Response: {res15.get('response')}")
        except Exception as e:
            logger.exception("Turn 15 failed with exception:")

if __name__ == "__main__":
    asyncio.run(run_diagnostic())

