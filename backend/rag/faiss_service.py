import faiss
import numpy as np
import os
import json
import uuid
from typing import List, Dict, Any, Optional
from loguru import logger

class FAISSService:
    def __init__(self, persist_directory: str = None, dimension: int = 384): # 384 for bge-small
        if persist_directory is None:
            # Always point to the project root /db/faiss
            current_file = os.path.abspath(__file__)
            # This file is in backend/rag/faiss_service.py, so go up 3 levels
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
            persist_directory = os.path.join(project_root, "db", "faiss")
            
        self.persist_directory = persist_directory
        self.dimension = dimension
        
        if not os.path.exists(persist_directory):
            os.makedirs(persist_directory)
            
        self.kb_index_path = os.path.join(persist_directory, "kb_index.faiss")
        self.kb_meta_path = os.path.join(persist_directory, "kb_meta.json")
        
        self.faq_index_path = os.path.join(persist_directory, "faq_index.faiss")
        self.faq_meta_path = os.path.join(persist_directory, "faq_meta.json")
        
        # Load or create KB index
        if os.path.exists(self.kb_index_path):
            self.kb_index = faiss.read_index(self.kb_index_path)
            with open(self.kb_meta_path, 'r') as f:
                self.kb_metadata = json.load(f)
        else:
            self.kb_index = faiss.IndexFlatIP(dimension) # Inner product for cosine similarity with normalized vectors
            self.kb_metadata = []
            
        # Load or create FAQ index
        if os.path.exists(self.faq_index_path):
            self.faq_index = faiss.read_index(self.faq_index_path)
            with open(self.faq_meta_path, 'r') as f:
                self.faq_metadata = json.load(f)
        else:
            self.faq_index = faiss.IndexFlatIP(dimension)
            self.faq_metadata = []

    def _normalize(self, v):
        norm = np.linalg.norm(v)
        if norm == 0:
            return v
        return v / norm

    def add_kb_chunks(self, chunks: List[Dict[str, Any]]):
        embeddings = []
        for chunk in chunks:
            # Normalize for cosine similarity via IndexFlatIP
            v = np.array(chunk['embedding'], dtype='float32')
            embeddings.append(self._normalize(v))
            
            self.kb_metadata.append({
                "id": chunk.get('id', str(uuid.uuid4())),
                "content": chunk['content'],
                "metadata": chunk.get('metadata', {})
            })
            
        self.kb_index.add(np.array(embeddings, dtype='float32'))
        
        # Save
        faiss.write_index(self.kb_index, self.kb_index_path)
        with open(self.kb_meta_path, 'w') as f:
            json.dump(self.kb_metadata, f)
            
        logger.info(f"Added {len(chunks)} chunks to FAISS KB index")

    def search_kb(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        if self.kb_index.ntotal == 0:
            return []
            
        v = np.array(query_embedding, dtype='float32')
        v = self._normalize(v).reshape(1, -1)
        
        distances, indices = self.kb_index.search(v, top_k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1: continue
            meta = self.kb_metadata[idx]
            results.append({
                "id": meta['id'],
                "content": meta['content'],
                "metadata": meta['metadata'],
                "score": float(dist) # In IndexFlatIP, this is cosine similarity if vectors were normalized
            })
        return results

    def add_faqs(self, faqs: List[Dict[str, Any]]):
        embeddings = []
        for faq in faqs:
            v = np.array(faq['embedding'], dtype='float32')
            embeddings.append(self._normalize(v))
            
            self.faq_metadata.append({
                "id": faq.get('id', str(uuid.uuid4())),
                "question": faq['question'],
                "answer": faq['answer'],
                "metadata": faq.get('metadata', {})
            })
            
        self.faq_index.add(np.array(embeddings, dtype='float32'))
        
        faiss.write_index(self.faq_index, self.faq_index_path)
        with open(self.faq_meta_path, 'w') as f:
            json.dump(self.faq_metadata, f)

    def search_faq(self, query_embedding: List[float], top_k: int = 3) -> List[Dict[str, Any]]:
        if self.faq_index.ntotal == 0:
            return []
            
        v = np.array(query_embedding, dtype='float32')
        v = self._normalize(v).reshape(1, -1)
        
        distances, indices = self.faq_index.search(v, top_k)
        
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1: continue
            meta = self.faq_metadata[idx]
            results.append({
                "question": meta['question'],
                "answer": meta['answer'],
                "metadata": meta['metadata'],
                "score": float(dist)
            })
        return results
