from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel

class ReviewPlan(BaseModel):
    scope: List[str]
    priority: Literal["low", "medium", "high"]
    reason: str
    required_context: List[str]

class ReviewPlanRequest(BaseModel):
    request: str
    repository_context: Optional[Dict[str, Any]] = None
