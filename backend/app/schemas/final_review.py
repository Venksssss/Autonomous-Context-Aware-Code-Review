"""
FinalReviewReport — the consolidated output produced by the Synthesizer Agent.

Design notes:
- Reuses the existing Finding model from agent_findings to keep a single
  representation flowing from specialists → synthesizer → final report.
- overall_risk is computed deterministically (no LLM involvement) using
  the severity ladder: critical > high > medium > low > none.
- analysis_metadata is populated by Python, never by the LLM.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel

from app.schemas.agent_findings import Finding

OverallRisk = Literal["critical", "high", "medium", "low", "none"]


class AnalysisMetadata(BaseModel):
    finding_count: int = 0
    security_findings: int = 0
    quality_findings: int = 0
    agents_used: List[str] = []


class FinalReviewReport(BaseModel):
    """
    Consolidated, developer-facing code review report.

    Produced by the Synthesizer Agent after all specialist agents have run.
    The raw specialist findings are still preserved in ReviewWorkflowResult.findings
    for transparency/debugging; this report offers the synthesized view.
    """
    summary: str
    overall_risk: OverallRisk
    findings: List[Finding] = []
    recommendations: List[str] = []
    files_reviewed: List[str] = []
    analysis_metadata: AnalysisMetadata = AnalysisMetadata()
