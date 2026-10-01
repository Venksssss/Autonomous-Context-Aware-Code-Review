import logging
from typing import Optional, Dict, Any
from app.schemas.agent_findings import AgentFindings
from app.prompts.security_agent import build_security_agent_messages
from app.services.llm.interface import LLMProvider
from app.services.llm.factory import create_llm_provider

logger = logging.getLogger(__name__)

class SecurityReviewerService:
    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or create_llm_provider()

    def generate_findings(self, review_request: str, diff_summary: dict, context: dict) -> AgentFindings:
        logger.info("Generating security findings")
        messages = build_security_agent_messages(review_request, diff_summary, context)
        
        try:
            findings = self.provider.structured_invoke(messages, AgentFindings)
            return findings
        except Exception as e:
            logger.error(f"Failed to generate security findings: {str(e)}")
            raise
