import os
import sys
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from loguru import logger
from sqlalchemy.orm import Session

# Add backend directory to path
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from database.session import SessionLocal
from database.models import EnterpriseDocument, DocumentSyncLog
from langchain_community.document_loaders import PyPDFLoader, TextLoader

class DocumentIngestionService:
    def __init__(self, watch_dir: str = None):
        self.db: Session = SessionLocal()
        if not watch_dir:
            # Default to the workspace knowledge-base directory
            self.watch_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge-base")
        else:
            self.watch_dir = watch_dir
            
        if not os.path.exists(self.watch_dir):
            os.makedirs(self.watch_dir, exist_ok=True)
            
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculates MD5 hash to detect updates."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    async def parse_document(self, file_path: str) -> str:
        """Parses a document (PDF or TXT) and returns the extracted text."""
        logger.info(f"Parsing enterprise document: {file_path}")
        if file_path.endswith('.pdf'):
            try:
                loader = PyPDFLoader(file_path)
                docs = loader.load()
                return "\n".join([doc.page_content for doc in docs])
            except Exception as e:
                logger.error(f"PyPDFLoader error on {file_path}: {e}")
                # Fallback simple text reader
                return f"Error loading PDF content: {str(e)}"
        elif file_path.endswith('.txt'):
            try:
                loader = TextLoader(file_path)
                docs = loader.load()
                return "\n".join([doc.page_content for doc in docs])
            except Exception as e:
                logger.error(f"TextLoader error on {file_path}: {e}")
                return ""
        else:
            logger.warning(f"Unsupported document format: {file_path}")
            return ""

    async def synchronize_enterprise_sources(self) -> Dict[str, Any]:
        """
        Scans configured enterprise folders, detects new/changed documents,
        hashes them, parses them, and updates metadata in PostgreSQL.
        """
        logger.info(f"Scanning enterprise repository: '{self.watch_dir}'")
        
        sync_log = DocumentSyncLog(
            sync_source=self.watch_dir,
            documents_detected=0,
            documents_processed=0,
            status="running"
        )
        self.db.add(sync_log)
        self.db.flush()
        
        files_detected = []
        files_processed = 0
        
        # Scan local directory (primary)
        for root, _, files in os.walk(self.watch_dir):
            for file in files:
                if file.endswith(('.pdf', '.txt')):
                    files_detected.append(os.path.join(root, file))

        sync_log.documents_detected = len(files_detected)
        logger.info(f"Detected {len(files_detected)} manuals in repository.")
        
        processed_documents = []
        
        for file_path in files_detected:
            try:
                file_hash = self._calculate_file_hash(file_path)
                
                # Check DB for existing hash
                existing_doc = self.db.query(EnterpriseDocument).filter(
                    EnterpriseDocument.file_path == file_path
                ).first()
                
                is_updated = False
                if not existing_doc:
                    logger.info(f"New document detected: {os.path.basename(file_path)}")
                    doc_record = EnterpriseDocument(
                        file_path=file_path,
                        file_hash=file_hash,
                        status="pending"
                    )
                    self.db.add(doc_record)
                    self.db.flush()
                    is_updated = True
                elif existing_doc.file_hash != file_hash:
                    logger.info(f"Modified document detected: {os.path.basename(file_path)}")
                    existing_doc.file_hash = file_hash
                    existing_doc.status = "pending"
                    doc_record = existing_doc
                    is_updated = True
                else:
                    logger.debug(f"Document unchanged: {os.path.basename(file_path)}")
                    doc_record = existing_doc
                    
                if is_updated:
                    # Parse document
                    text_content = await self.parse_document(file_path)
                    if text_content.strip():
                        doc_record.status = "parsed"
                        doc_record.error_message = None
                        files_processed += 1
                        processed_documents.append({
                            "id": doc_record.id,
                            "file_path": file_path,
                            "content": text_content
                        })
                    else:
                        doc_record.status = "failed"
                        doc_record.error_message = "Parsed content is empty"
                
                self.db.commit()
            except Exception as e:
                logger.error(f"Error synchronizing file {file_path}: {e}")
                self.db.rollback()
                
        sync_log.documents_processed = files_processed
        sync_log.status = "completed"
        self.db.commit()
        
        logger.info(f"Sync complete. Processed/Updated {files_processed} files.")
        return {
            "sync_log_id": sync_log.id,
            "documents_detected": len(files_detected),
            "documents_processed": files_processed,
            "processed_documents": processed_documents
        }

    # Connector Placeholders for SharePoint, Confluence, S3 and Git integration
    async def sync_sharepoint_connector(self, site_url: str, folder_path: str) -> None:
        logger.info(f"Syncing SharePoint Site: {site_url} / {folder_path} ...")
        # In a fully deployed client build, we authenticate using Graph API and download files locally
        pass

    async def sync_s3_connector(self, bucket_name: str, prefix: str) -> None:
        logger.info(f"Syncing Amazon S3 Bucket: {bucket_name}/{prefix} ...")
        # Download files from S3 bucket using boto3 and trigger local parse
        pass

    async def sync_confluence_connector(self, space_key: str) -> None:
        logger.info(f"Syncing Confluence space: {space_key} ...")
        # Query Confluence REST API pages and convert them to txt before syncing
        pass

if __name__ == "__main__":
    import asyncio
    service = DocumentIngestionService()
    asyncio.run(service.synchronize_enterprise_sources())
