from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from loguru import logger
import json

from rag.vector_search_service import VectorSearchService
from integrations.ollama_service import OllamaService
from services.intent_classifier import IntentClassifier
from prompts.rag_prompts import RAG_PROMPT_TEMPLATE, SYSTEM_PROMPT, FALLBACK_PROMPT

class RAGPipeline:
    def __init__(self, db: Session):
        self.search_service = VectorSearchService(db)
        self.llm_service = OllamaService()
        self.intent_classifier = IntentClassifier()

    async def process_query(self, query: str, session_history: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Main orchestration method for RAG.
        1. Retrieve context
        2. Evaluate confidence
        3. Generate response
        """
        logger.info(f"Processing RAG query: {query}")
        
        # 0. Intent Classification
        intent = await self.intent_classifier.classify_intent(query)
        logger.info(f"Detected intent: {intent}")
        
        if intent == "GREETING":
            response = await self.llm_service.generate_response(f"The user said: {query}. Respond with a friendly greeting and ask how you can help them with their IT issues today.", SYSTEM_PROMPT)
            return {
                "response": response,
                "sources": [],
                "confidence": 1.0,
                "needs_ticket": False
            }
        
        # Clean/rewrite query if it contains attached file content to improve vector similarity matching
        search_query = query
        if "Attached Image Content" in query or "Attached Document Content" in query:
            import re
            match = re.search(r"\[Attached (?:Image|Document) Content:\s*(.*?)\]", query)
            if match:
                extracted = match.group(1).strip()
                # Clean up any surrounding whitespace or formatting
                if extracted:
                    search_query = extracted
                    logger.info(f"Extracted attached content for search: '{search_query}'")

        # 1. Search Knowledge Base
        kb_results = self.search_service.search_kb(search_query, top_k=3)
        
        # 2. Search FAQs
        faq_results = self.search_service.search_faq(search_query, top_k=2)
        
        # 3. Search Historical Tickets
        ticket_results = self.search_service.search_historical_tickets(query, top_k=2)
        
        # Merge results
        all_results = kb_results + faq_results + ticket_results
        
        # Filter low confidence results
        valid_results = [r for r in all_results if r['score'] > 0.40] # more lenient threshold for testing
        
        sources = []
        context_parts = []
        
        if not valid_results:
            logger.warning("No high confidence context found. Using fallback.")
            return {
                "response": FALLBACK_PROMPT,
                "sources": [],
                "confidence": 0.0,
                "needs_ticket": True
            }
            
        # Build context string
        for idx, res in enumerate(valid_results):
            if res['type'] == 'kb_article':
                context_parts.append(f"[Source {idx+1}: {res['title']}]\n{res['content']}")
                sources.append({"id": idx+1, "title": res['title'], "type": "kb"})
            elif res['type'] == 'faq':
                context_parts.append(f"[Source {idx+1}: FAQ]\nQ: {res['question']}\nA: {res['answer']}")
                sources.append({"id": idx+1, "title": "FAQ", "type": "faq"})
            elif res['type'] == 'historical_ticket':
                context_parts.append(f"[Source {idx+1}: Past Ticket {res['ticket_id']}]\nIssue: {res['description']}\nResolution: {res['resolution']}")
                sources.append({"id": idx+1, "title": f"Ticket {res['ticket_id']}", "type": "ticket"})

        context_str = "\n\n---\n\n".join(context_parts)
        
        # Optionally incorporate conversation memory here by prepending to context
        history_context = ""
        if session_history:
            history_parts = []
            for msg in session_history[-5:]: # last 5 messages
                role = "User" if msg['role'] == 'user' else "Assistant"
                history_parts.append(f"{role}: {msg['content']}")
            history_context = "Previous Conversation:\n" + "\n".join(history_parts) + "\n\n"
        
        full_context = history_context + context_str
        
        prompt = RAG_PROMPT_TEMPLATE.format(context=full_context, question=query)
        
        # Generate response
        response = await self.llm_service.generate_response(prompt, SYSTEM_PROMPT)
        
        # Post-process response to clean up any LaTeX or raw unicode arrows
        if response:
            response = response.replace(r"$\rightarrow$", " then go to ").replace(r"\rightarrow", " then go to ")
            response = response.replace(" ➔ ", " then go to ").replace("➔", " then go to ")
            response = response.replace(" -> ", " then go to ").replace("->", " then go to ")
            response = response.replace(" 🡪 ", " then go to ").replace("🡪", " then go to ")
            # Remove redundant URL navigation instructions
            response = response.replace("Navigate to the Elixir Portal URL, then go to ", "Go to ")
            response = response.replace("Navigate to the Elixir Portal URL then go to ", "Go to ")
            response = response.replace("navigate to the Elixir Portal URL, then go to ", "Go to ")
            response = response.replace("navigate to the Elixir Portal URL then go to ", "Go to ")
            response = response.replace("In the URL, click on ", "Go to ")
            response = response.replace("In the URL, navigate to ", "Go to ")

            # Remove comparative system notes comparing Elixir Portal vs SAP MDG
            for phrase in [
                "Please note that SAP master data procedures, including Location Data Extensions, are performed inside SAP MDG and not within the Elixir Portal.",
                "Please note that SAP master data procedures, such as Location Data Extension, are performed inside SAP MDG and not in the Elixir Portal.",
                "Please note that SAP master data procedures, such as Location Data Extension, are performed inside SAP MDG and not within the Elixir Portal.",
                "Please note that SAP master data procedures, including Location Data Extensions, are performed inside SAP MDG and not in the Elixir Portal.",
                "SAP master data procedures, including Location Data Extensions, are performed inside SAP MDG and not within the Elixir Portal.",
                "SAP master data procedures, such as Location Data Extension, are performed inside SAP MDG and not in the Elixir Portal.",
                "Please note that SAP master data procedures are performed inside SAP MDG and not within the Elixir Portal.",
                "Please note that SAP master data procedures are performed inside SAP MDG and not in the Elixir Portal.",
            ]:
                response = response.replace(phrase, "")




        
        # Confidence heuristic based on top score
        top_score = valid_results[0]['score'] if valid_results else 0.0
        
        # Suggest ticket if score is borderline
        needs_ticket = False
        if top_score < 0.75:
            needs_ticket = True
            
        return {
            "response": response,
            "sources": sources,
            "confidence": top_score,
            "needs_ticket": needs_ticket
        }

    async def generate_streaming_response(self, query: str, context: str):
        prompt = RAG_PROMPT_TEMPLATE.format(context=context, question=query)
        async for chunk in self.llm_service.generate_stream(prompt, SYSTEM_PROMPT):
            yield chunk
