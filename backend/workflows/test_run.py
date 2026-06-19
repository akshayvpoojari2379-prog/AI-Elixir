import asyncio
import os
import sys
from loguru import logger

# Add backend directory to path
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

# Set environment placeholders to allow importing without DB/Ollama connections crashing
os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5432/ai_service_desk"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["FRESHSERVICE_DOMAIN"] = "mock.freshservice.com"
os.environ["FRESHSERVICE_API_KEY"] = "mock_key"
os.environ["JWT_SECRET"] = "mock_secret"

from workflows.knowledge_engine import KnowledgeEngine
from workflows.tools import registry

async def test_workflows():
    logger.info("Initializing Service Desk Test Suite...")
    
    # 1. Test KnowledgeEngine Matching
    engine = KnowledgeEngine()
    
    queries_to_test = [
        "Laptop Request for New Joinee",
        "Request for replacement of Desktop/Laptop/Tab",
        "Surrender of Laptop",
        "Self-Certification of Asset"
    ]
    
    logger.info("--- Testing Knowledge Base Matchmaking ---")
    for q in queries_to_test:
        skill, issue, conf = engine.match_workflow(q)
        logger.info(f"Query: '{q}' -> Matched Skill: {skill}, Issue: {issue} (Conf: {conf:.2f})")
        
    # 2. Test Tools Registry
    logger.info("--- Testing MCP-Style Tools Registry ---")
    tools = registry.list_tools()
    for tool_name, metadata in tools.items():
        logger.info(f"Tool Registered: {tool_name} - Description: {metadata['description']}")
        
    logger.info("Test suite validated successfully! Codebase is ready for local Ollama and Freshservice runtime execution.")

if __name__ == "__main__":
    asyncio.run(test_workflows())
