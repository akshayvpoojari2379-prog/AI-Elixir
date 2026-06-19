import sys
import os
import argparse
from loguru import logger

# Add backend to path for importing models and services
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from database.session import SessionLocal
from database.models import KBArticle, KBChunk, FAQEmbedding
from ingestion.document_loader import DocumentLoader
from ingestion.chunking_service import ChunkingService
from embeddings.embedding_service import EmbeddingService
from rag.faiss_service import FAISSService

class IngestionPipeline:
    def __init__(self):
        self.loader = DocumentLoader()
        self.chunker = ChunkingService()
        self.embedder = EmbeddingService()
        self.faiss_service = FAISSService()
        self.db = SessionLocal()

    def process_kb_directory(self, directory_path: str):
        logger.info(f"Starting KB ingestion from {directory_path}")
        
        # 1. Load documents
        documents = self.loader.load_directory(directory_path)
        if not documents:
            logger.warning("No documents found to process.")
            return

        # 2. Chunk documents
        chunks = self.chunker.chunk_documents(documents)
        
        # 3. Generate embeddings and store
        self._store_kb_chunks(chunks)
        
        logger.info("KB Ingestion complete!")

    def process_faq_directory(self, directory_path: str):
        logger.info(f"Starting FAQ ingestion from {directory_path}")
        
        documents = self.loader.load_directory(directory_path)
        if not documents:
            logger.warning("No FAQ documents found.")
            return
            
        chunks = self.chunker.chunk_documents(documents)
        
        # For FAQs we might just treat them as small chunks with question/answer
        # Simplified handling here: assume chunks are question/answer pairs
        self._store_faq_chunks(chunks)
        
        logger.info("FAQ Ingestion complete!")

    def _store_kb_chunks(self, chunks):
        # We need to extract unique articles first
        articles_map = {}
        for chunk in chunks:
            source = chunk.metadata.get('source_file')
            if source not in articles_map:
                # Create article record
                article = KBArticle(
                    source_file=source,
                    title=os.path.basename(source),
                    category=chunk.metadata.get('category', 'General'),
                    document_type=chunk.metadata.get('document_type', 'UNKNOWN')
                )
                self.db.add(article)
                self.db.commit()
                self.db.refresh(article)
                articles_map[source] = article

        # Generate embeddings in batch
        texts = [chunk.page_content for chunk in chunks]
        embeddings = self.embedder.generate_batch_embeddings(texts)
        
        # Create chunk records
        db_chunks = []
        for i, chunk in enumerate(chunks):
            article = articles_map[chunk.metadata.get('source_file')]
            db_chunk = KBChunk(
                article_id=article.id,
                content=chunk.page_content,
                embedding=embeddings[i],
                chunk_index=chunk.metadata.get('chunk_index', 0)
            )
            db_chunks.append(db_chunk)
            
        self.db.bulk_save_objects(db_chunks)
        self.db.commit()
        
        # 4. Also store in FAISS for retrieval
        faiss_chunks = []
        for i, chunk in enumerate(chunks):
            faiss_chunks.append({
                "content": chunk.page_content,
                "embedding": embeddings[i],
                "metadata": {
                    "title": os.path.basename(chunk.metadata.get('source_file')),
                    "source_file": chunk.metadata.get('source_file')
                }
            })
        self.faiss_service.add_kb_chunks(faiss_chunks)
        
        logger.info(f"Stored {len(db_chunks)} chunks in database and FAISS index.")

    def _store_faq_chunks(self, chunks):
        texts = [chunk.page_content for chunk in chunks]
        embeddings = self.embedder.generate_batch_embeddings(texts)
        
        faq_records = []
        for i, chunk in enumerate(chunks):
            # Simplification: storing the chunk as both question and answer for generic docs
            # Or you can parse it if it's strictly Q&A format.
            faq = FAQEmbedding(
                question=chunk.page_content[:200] + "...", # rough approximation
                answer=chunk.page_content,
                category=chunk.metadata.get('category', 'FAQ'),
                source_file=chunk.metadata.get('source_file'),
                embedding=embeddings[i]
            )
            faq_records.append(faq)
            
        self.db.bulk_save_objects(faq_records)
        self.db.commit()

        # Also store in FAISS
        faiss_faqs = []
        for i, chunk in enumerate(chunks):
            faiss_faqs.append({
                "question": chunk.page_content[:200],
                "answer": chunk.page_content,
                "embedding": embeddings[i],
                "metadata": {"source_file": chunk.metadata.get('source_file')}
            })
        self.faiss_service.add_faqs(faiss_faqs)
        
        logger.info(f"Stored {len(faq_records)} FAQs in database and FAISS index.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into pgvector")
    parser.add_argument("--kb-dir", type=str, help="Directory containing KB articles")
    parser.add_argument("--faq-dir", type=str, help="Directory containing FAQs")
    args = parser.parse_args()
    
    pipeline = IngestionPipeline()
    if args.kb_dir:
        pipeline.process_kb_directory(args.kb_dir)
    if args.faq_dir:
        pipeline.process_faq_directory(args.faq_dir)
