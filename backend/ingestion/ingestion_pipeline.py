import os
import argparse
from loguru import logger
from sqlalchemy.orm import Session
import uuid

from database.session import SessionLocal
from database.models import KBArticle, KBChunk
from ingestion.document_processor import DocumentProcessor
from embeddings.embedding_service import EmbeddingService
from rag.faiss_service import FAISSService

class IngestionPipeline:
    def __init__(self):
        self.processor = DocumentProcessor()
        self.embedder = EmbeddingService()
        self.vector_db = FAISSService()
        self.db: Session = SessionLocal()

    def ingest_kb_directory(self, directory_path: str, category: str = "General"):
        logger.info(f"Starting KB ingestion from: {directory_path}")
        
        if not os.path.exists(directory_path):
            logger.error(f"Directory not found: {directory_path}")
            return

        for root, _, files in os.walk(directory_path):
            for file in files:
                if not file.endswith(('.pdf', '.txt', '.docx', '.doc')):
                    continue
                    
                file_path = os.path.join(root, file)
                
                # 1. Process document into chunks
                chunks = self.processor.process_file(file_path)
                if not chunks:
                    continue

                # 2. Save Article metadata to Postgres
                article = KBArticle(
                    title=file,
                    category=category,
                    source_file=file,
                    tags=[]
                )
                self.db.add(article)
                self.db.flush() # Get the article.id

                # 3. Generate embeddings and save chunks to FAISS
                faiss_chunks = []
                for chunk in chunks:
                    embedding = self.embedder.generate_embedding(chunk['content'])
                    
                    faiss_chunks.append({
                        "id": str(uuid.uuid4()),
                        "content": chunk['content'],
                        "embedding": embedding,
                        "metadata": {
                            "article_id": str(article.id),
                            "title": file,
                            "source_file": file,
                            **chunk['metadata']
                        }
                    })
                
                self.vector_db.add_kb_chunks(faiss_chunks)
                
        self.db.commit()
        logger.info("Ingestion completed successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into the AI Service Desk")
    parser.add_argument("--kb-dir", type=str, help="Directory containing KB articles")
    parser.add_argument("--category", type=str, default="General", help="Category for ingested articles")
    
    args = parser.parse_args()
    
    pipeline = IngestionPipeline()
    if args.kb_dir:
        pipeline.ingest_kb_directory(args.kb_dir, args.category)
    else:
        print("Please provide a directory path using --kb-dir")
