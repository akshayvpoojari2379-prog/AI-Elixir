import os
import sys
from typing import Dict, Any, List
from loguru import logger
from sqlalchemy.orm import Session

# Add backend directory to path
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from database.session import SessionLocal
from database.models import EnterpriseDocument
from ingestion.document_ingestion_service import DocumentIngestionService
from workflows.domain_classifier import DomainClassifier
from workflows.workflow_extractor import WorkflowExtractor
from workflows.skillset_generator import SkillsetGenerator

class KnowledgeStructurer:
    def __init__(self):
        self.db: Session = SessionLocal()
        self.ingestion_service = DocumentIngestionService()
        self.domain_classifier = DomainClassifier()
        self.workflow_extractor = WorkflowExtractor()
        self.skill_generator = SkillsetGenerator()

    async def structure_knowledge(self, file_path: str, content: str, doc_id: Any = None) -> Dict[str, Any]:
        """
        Coordinates full processing of parsed document text:
        1. Classifies the Operational Domain.
        2. Extracts the structured Workflow / SOP Steps.
        3. Dynamically generates the Skillset and registers it.
        """
        logger.info(f"Structuring knowledge for file: {os.path.basename(file_path)}...")
        
        # 1. Classify operational domain
        domain_data = await self.domain_classifier.classify_domain(content)
        
        # 2. Extract workflow steps & variables
        workflow_data = await self.workflow_extractor.extract_workflow(doc_id, content)
        
        # 3. Dynamically generate and register the ReAct skill agent
        skill_record = await self.skill_generator.generate_skillset(workflow_data, domain_data)
        
        return {
            "file_path": file_path,
            "domain": domain_data,
            "workflow": workflow_data,
            "skillset": skill_record
        }

    async def structure_all_pending_documents(self) -> List[Dict[str, Any]]:
        """
        Scans for parsed documents in PostgreSQL, structures them,
        and runs the full workflow extraction + agent generation pipeline.
        """
        logger.info("Scanning for parsed enterprise manuals to structure...")
        
        pending_docs = self.db.query(EnterpriseDocument).filter(
            EnterpriseDocument.status == "parsed"
        ).all()
        
        logger.info(f"Found {len(pending_docs)} pending manuals to process.")
        results = []
        
        for doc in pending_docs:
            try:
                # 1. Parse text content
                text_content = await self.ingestion_service.parse_document(doc.file_path)
                if not text_content.strip():
                    doc.status = "failed"
                    doc.error_message = "Parsed text content is empty."
                    self.db.commit()
                    continue
                    
                # 2. Run structuring pipeline
                struct_res = await self.structure_knowledge(doc.file_path, text_content, doc.id)
                
                # Associate the document ID in the workflow
                doc.status = "parsed"
                doc.error_message = None
                self.db.commit()
                
                results.append(struct_res)
                logger.info(f"Successfully processed and generated agent for {os.path.basename(doc.file_path)}")
            except Exception as e:
                logger.error(f"Failed to process manual {doc.file_path}: {e}")
                doc.status = "failed"
                doc.error_message = str(e)
                self.db.commit()
                
        return results

if __name__ == "__main__":
    import asyncio
    structurer = KnowledgeStructurer()
    asyncio.run(structurer.structure_all_pending_documents())
