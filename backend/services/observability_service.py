import os
import sys
import time
from typing import Dict, Any, List
from loguru import logger
from sqlalchemy import func
from sqlalchemy.orm import Session

# Add backend directory to path
backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(backend_path)

from database.session import SessionLocal
from database.models import RoutingLog, EnterpriseDocument, SkillRegistry, ExtractedWorkflow, ChatSession

class ObservabilityService:
    def __init__(self):
        self.db: Session = SessionLocal()

    async def log_routing_decision(
        self,
        session_id: Any,
        query: str,
        matched_skill: str,
        confidence_score: float,
        routing_history: List[str],
        latency_ms: int
    ) -> RoutingLog:
        """Logs a multi-agent state transition decision in PostgreSQL."""
        logger.info(f"Observability Log: Routed session {session_id} to '{matched_skill}' in {latency_ms}ms")
        
        log = RoutingLog(
            session_id=session_id,
            query=query,
            matched_skill=matched_skill,
            confidence_score=confidence_score,
            routing_history=routing_history,
            latency_ms=latency_ms
        )
        try:
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.error(f"Failed to commit routing observability log: {e}")
            self.db.rollback()
            
        return log

    async def get_metrics(self) -> Dict[str, Any]:
        """ Gathers complete operational and sync metrics from PostgreSQL tables. """
        metrics = {
            "total_documents_synced": 0,
            "parsed_documents_count": 0,
            "total_dynamic_skillsets": 0,
            "total_extracted_workflows": 0,
            "total_conversations": 0,
            "average_routing_confidence": 0.0,
            "average_routing_latency_ms": 0.0,
            "skill_routing_distribution": {}
        }
        
        try:
            # 1. Document Sync Counts
            metrics["total_documents_synced"] = self.db.query(EnterpriseDocument).count()
            metrics["parsed_documents_count"] = self.db.query(EnterpriseDocument).filter(
                EnterpriseDocument.status == "parsed"
            ).count()
            
            # 2. Dynamic Agents & Workflows
            metrics["total_dynamic_skillsets"] = self.db.query(SkillRegistry).count()
            metrics["total_extracted_workflows"] = self.db.query(ExtractedWorkflow).count()
            
            # 3. Conversations
            metrics["total_conversations"] = self.db.query(ChatSession).count()
            
            # 4. Latency and Confidence averages
            avg_conf = self.db.query(func.avg(RoutingLog.confidence_score)).scalar()
            avg_lat = self.db.query(func.avg(RoutingLog.latency_ms)).scalar()
            
            metrics["average_routing_confidence"] = round(float(avg_conf or 0.0), 2)
            metrics["average_routing_latency_ms"] = round(float(avg_lat or 0.0), 2)
            
            # 5. Routing Distribution
            dist = self.db.query(
                RoutingLog.matched_skill,
                func.count(RoutingLog.id)
            ).group_by(RoutingLog.matched_skill).all()
            
            metrics["skill_routing_distribution"] = {row[0]: row[1] for row in dist}
            
        except Exception as e:
            logger.error(f"Error gathering observability metrics: {e}")
            
        return metrics

if __name__ == "__main__":
    import asyncio
    service = ObservabilityService()
    print(asyncio.run(service.get_metrics()))
