from typing import List
from sentence_transformers import SentenceTransformer
from loguru import logger
import torch
from tenacity import retry, stop_after_attempt, wait_exponential

class EmbeddingService:
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5"):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading embedding model {model_name} on {self.device}...")
        self.model = SentenceTransformer(model_name, device=self.device)
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text string."""
        return self.model.encode(text, normalize_embeddings=True).tolist()
        
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate_batch_embeddings(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Generate embeddings for a list of texts in batches."""
        logger.info(f"Generating embeddings for {len(texts)} texts in batches of {batch_size}...")
        embeddings = self.model.encode(
            texts, 
            batch_size=batch_size, 
            show_progress_bar=True,
            normalize_embeddings=True
        )
        return embeddings.tolist()
