import logging
from typing import Optional, Dict, Any
from app.schemas.agent_findings import AgentFindings
from app.prompts.quality_agent import build_quality_agent_messages
from app.services.llm.interface import LLMProvider
from app.services.llm.factory import create_llm_provider

logger = logging.getLogger(__name__)

class QualityReviewerService:
    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or create_llm_provider()

    def generate_findings(self, review_request: str, diff_summary: dict, context: dict) -> AgentFindings:
        logger.info("Generating quality findings")
        messages = build_quality_agent_messages(review_request, diff_summary, context)
        
        try:
            findings = self.provider.structured_invoke(messages, AgentFindings)
            return findings
        except Exception as e:
            logger.error(f"Failed to generate quality findings: {str(e)}")
            raise
