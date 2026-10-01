from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel
from app.schemas.review_planner import ReviewPlan


class ReviewWorkflowRequest(BaseModel):
    """
    Request schema for POST /api/ai/review.
    repository_path / base_revision / head_revision are optional to allow
    planner-only mode (useful when callers supply diff context externally).
    """
    review_request: str
    repository_path: Optional[str] = None
    base_revision: Optional[str] = None
    head_revision: Optional[str] = None


class ReviewWorkflowResult(BaseModel):
    """
    Workflow execution result.

    Distinct from ReviewPlan:
      ReviewPlan    = the planner's AI output (scope, priority, reason, …)
      ReviewWorkflowResult = envelope describing the overall workflow run
    """
    status: Literal["planned", "failed"]
    review_plan: Optional[ReviewPlan] = None
    errors: List[str] = []
