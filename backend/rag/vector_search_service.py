from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from loguru import logger
import json

from database.models import KBChunk, FAQEmbedding, TicketResolutionEmbedding, KBArticle
from embeddings.embedding_service import EmbeddingService
from rag.faiss_service import FAISSService

class VectorSearchService:
    def __init__(self, db: Session):
        self.db = db
        self.embedder = EmbeddingService()
        self.vector_db = FAISSService()

    def search_kb(self, query: str, top_k: int = 5, threshold: float = 0.5, category: Optional[str] = None) -> List[Dict[str, Any]]:
        logger.info(f"Searching KB for query: '{query}'")
        query_embedding = self.embedder.generate_embedding(query)
        
        # Search in FAISS
        results = self.vector_db.search_kb(query_embedding, top_k=top_k)
        logger.info(f"FAISS found {len(results)} results")
        
        formatted_results = []
        for res in results:
            similarity = res['score']
            logger.info(f"Result score: {similarity:.4f} | Content snippet: {res['content'][:50]}...")
            
            if similarity < threshold:
                continue
                
            formatted_results.append({
                "content": res['content'],
                "title": res['metadata'].get('title', 'Unknown'),
                "source": res['metadata'].get('source_file', 'Unknown'),
                "score": float(similarity),
                "type": "kb_article"
            })
            
        return formatted_results

    def search_faq(self, query: str, top_k: int = 3, threshold: float = 0.5) -> List[Dict[str, Any]]:
        logger.info(f"Searching FAQs for query: '{query}'")
        query_embedding = self.embedder.generate_embedding(query)
        
        results = self.vector_db.search_faq(query_embedding, top_k=top_k)
        
        formatted_results = []
        for res in results:
            similarity = res['score']
            if similarity < threshold:
                continue
                
            formatted_results.append({
                "question": res['question'],
                "answer": res['answer'],
                "source": res['metadata'].get('source_file', 'Unknown'),
                "score": float(similarity),
                "type": "faq"
            })
            
        return formatted_results

    def search_historical_tickets(self, query: str, top_k: int = 3, threshold: float = 0.6) -> List[Dict[str, Any]]:
        logger.info(f"Searching historical tickets for query: '{query}'")
        # Placeholder
        return []
