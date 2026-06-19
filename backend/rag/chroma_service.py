import chromadb
from chromadb.config import Settings
import os
from typing import List, Dict, Any, Optional
from loguru import logger

class ChromaService:
    def __init__(self, persist_directory: str = "db/chroma"):
        self.persist_directory = persist_directory
        if not os.path.exists(persist_directory):
            os.makedirs(persist_directory)
            
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Initialize collections
        self.kb_collection = self.client.get_or_create_collection(name="kb_articles")
        self.faq_collection = self.client.get_or_create_collection(name="faqs")
        self.ticket_collection = self.client.get_or_create_collection(name="historical_tickets")
        
        logger.info(f"ChromaDB initialized at {persist_directory}")

    def add_kb_chunks(self, chunks: List[Dict[str, Any]]):
        """
        chunks: list of dicts with {id, content, embedding, metadata}
        """
        ids = [c['id'] for c in chunks]
        documents = [c['content'] for c in chunks]
        embeddings = [c['embedding'] for c in chunks]
        metadatas = [c['metadata'] for c in chunks]
        
        self.kb_collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
        logger.info(f"Added {len(chunks)} chunks to KB collection")

    def search_kb(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        results = self.kb_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        formatted = []
        # Results are lists of lists because we passed a list of query_embeddings
        for i in range(len(results['ids'][0])):
            formatted.append({
                "id": results['ids'][0][i],
                "content": results['documents'][0][i],
                "metadata": results['metadatas'][0][i],
                "distance": results['distances'][0][i]
            })
        return formatted

    def add_faqs(self, faqs: List[Dict[str, Any]]):
        ids = [f['id'] for f in faqs]
        documents = [f['question'] + " " + f['answer'] for f in faqs]
        embeddings = [f['embedding'] for f in faqs]
        metadatas = [f['metadata'] for f in faqs]
        
        self.faq_collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )

    def search_faq(self, query_embedding: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
        results = self.faq_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        formatted = []
        for i in range(len(results['ids'][0])):
            formatted.append({
                "content": results['documents'][0][i],
                "metadata": results['metadatas'][0][i],
                "distance": results['distances'][0][i]
            })
        return formatted
