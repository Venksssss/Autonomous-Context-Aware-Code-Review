from typing import List, Literal, Optional
from pydantic import BaseModel

FindingCategory = Literal["security", "logic", "quality", "performance"]
FindingSeverity = Literal["critical", "high", "medium", "low", "info"]

class Finding(BaseModel):
    id: str
    category: FindingCategory
    severity: FindingSeverity
    title: str
    description: str
    file_path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    evidence: List[str]
    recommendation: str
    confidence: Optional[float] = None
    source_agent: str

class AgentFindings(BaseModel):
    findings: List[Finding]
