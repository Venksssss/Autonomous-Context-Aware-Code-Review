import logging
from typing import Optional, Dict, Any
from app.schemas.review_planner import ReviewPlan
from app.prompts.review_planner import build_review_planner_messages
from app.services.llm.interface import LLMProvider
from app.services.llm.factory import create_llm_provider

logger = logging.getLogger(__name__)

class ReviewPlannerService:
    def __init__(self, provider: Optional[LLMProvider] = None):
        # Support dependency injection for tests
        self.provider = provider or create_llm_provider()

    def generate_plan(self, request: str, repository_context: Optional[Dict[str, Any]] = None) -> ReviewPlan:
        logger.info("Generating review plan")
        messages = build_review_planner_messages(request, repository_context)
        
        try:
            plan = self.provider.structured_invoke(messages, ReviewPlan)
            logger.info("Review plan successfully generated")
            return plan
        except Exception as e:
            logger.error(f"Failed to generate review plan: {str(e)}")
            raise
