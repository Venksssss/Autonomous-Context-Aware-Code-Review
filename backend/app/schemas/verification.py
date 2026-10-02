from typing import List, Literal, Optional
from pydantic import BaseModel
from app.schemas.test_run import TestExecutionResult

VerificationStatus = Literal["verified", "contradicted", "inconclusive", "not_tested"]

class VerificationResult(BaseModel):
    finding_id: str
    verification_status: VerificationStatus
    runtime_evidence: Optional[TestExecutionResult] = None
    supporting_tests: List[str] = []
    explanation: str

class AgentVerificationOutput(BaseModel):
    verification_results: List[VerificationResult] = []
