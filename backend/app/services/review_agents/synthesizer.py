"""
SynthesizerService — consolidates specialist findings into a FinalReviewReport.

Design rules:
  - Uses LLMProvider.structured_invoke for deduplication and summary generation.
  - overall_risk and analysis_metadata are computed deterministically by Python,
    not by the LLM (avoids hallucinated counts / risk escalation).
  - files_reviewed is derived deterministically from diff/context/findings;
    the LLM never decides this list.
  - The synthesizer must NOT perform fresh repository exploration.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.schemas.agent_findings import Finding
from app.schemas.final_review import (
    AnalysisMetadata, FinalReviewReport, OverallRisk,
    RuntimeSummary, VerificationSummary
)
from app.schemas.verification import VerificationResult
from app.prompts.synthesizer import build_synthesizer_messages
from app.services.llm.interface import LLMProvider
from app.services.llm.factory import create_llm_provider

logger = logging.getLogger(__name__)

# Severity ordering used for deterministic overall_risk aggregation.
_SEVERITY_RANK: Dict[str, int] = {
    "critical": 5,
    "high": 4,
    "medium": 3,
    "low": 2,
    "info": 1,
}

_RANK_TO_RISK: Dict[int, OverallRisk] = {
    5: "critical",
    4: "high",
    3: "medium",
    2: "low",
    1: "low",
    0: "none",
}


def compute_overall_risk(findings: List[Finding]) -> OverallRisk:
    """
    Deterministically derive overall risk from findings.

    Policy (transparent, not LLM-based):
      critical finding  → overall critical
      else high         → overall high
      else medium       → overall medium
      else low/info     → overall low
      no findings       → overall none
    """
    if not findings:
        return "none"
    max_rank = max(
        _SEVERITY_RANK.get(f.severity, 0) for f in findings
    )
    return _RANK_TO_RISK.get(max_rank, "none")


def extract_files_reviewed(
    diff_summary: Optional[Dict[str, Any]],
    context: Optional[Dict[str, Any]],
    findings: List[Finding],
) -> List[str]:
    """
    Deterministically collect the set of files involved in this review.

    Priority order:
    1. Files from the git diff (primary source of truth)
    2. Files referenced in the context agent output
    3. Files referenced in specialist findings (fallback)
    """
    files: set[str] = set()

    if diff_summary:
        for f in diff_summary.get("changed_files", []):
            if isinstance(f, str) and f:
                files.add(f)

    if context:
        for f in context.get("changed_files", []):
            if isinstance(f, str) and f:
                files.add(f)
        for f in context.get("related_files", []):
            if isinstance(f, str) and f:
                files.add(f)

    for finding in findings:
        if finding.file_path:
            files.add(finding.file_path)

    return sorted(files)


def build_analysis_metadata(
    findings: List[Finding],
    agents_used: Optional[List[str]] = None,
) -> AnalysisMetadata:
    """Build metadata deterministically from findings (never via LLM)."""
    security_count = sum(1 for f in findings if f.category == "security")
    quality_count = sum(
        1 for f in findings if f.category in ("logic", "quality", "performance")
    )
    return AnalysisMetadata(
        finding_count=len(findings),
        security_findings=security_count,
        quality_findings=quality_count,
        agents_used=agents_used or ["planner", "context", "security", "quality", "synthesizer"],
    )

def build_runtime_summary(runtime_test_result: Optional[Dict[str, Any]]) -> Optional[RuntimeSummary]:
    if not runtime_test_result:
        return None
    return RuntimeSummary(
        status=runtime_test_result.get("status", "unknown"),
        tests_run=runtime_test_result.get("tests_run") or 0,
        tests_passed=runtime_test_result.get("tests_passed") or 0,
        tests_failed=runtime_test_result.get("tests_failed") or 0,
        tests_errors=runtime_test_result.get("tests_errors") or 0,
        execution_mode=runtime_test_result.get("execution_mode", "local"),
        sandboxed=runtime_test_result.get("sandboxed", False),
        duration_seconds=runtime_test_result.get("duration_seconds", 0.0),
    )

def build_verification_summary(verification_results: List[Dict[str, Any]]) -> VerificationSummary:
    summary = VerificationSummary()
    for v in verification_results:
        status = v.get("verification_status")
        if status == "verified":
            summary.verified += 1
        elif status == "contradicted":
            summary.contradicted += 1
        elif status == "inconclusive":
            summary.inconclusive += 1
        elif status == "not_tested":
            summary.not_tested += 1
    return summary


# ---------------------------------------------------------------------------
# Intermediate schema the LLM fills in (subset of FinalReviewReport)
# We ask the LLM only for the parts it is good at: deduplication + prose.
# Deterministic fields (overall_risk, files_reviewed, metadata) are added
# by Python after the LLM responds.
# ---------------------------------------------------------------------------
from pydantic import BaseModel  # noqa: E402

class _SynthesizerLLMOutput(BaseModel):
    """
    The structured output we request from the LLM.
    Kept intentionally minimal to reduce hallucination surface.
    """
    summary: str
    findings: List[Finding] = []
    recommendations: List[str] = []


class SynthesizerService:
    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider or create_llm_provider()

    def synthesize(
        self,
        review_request: str,
        review_plan: Optional[Dict[str, Any]],
        diff_summary: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
        raw_findings: List[Dict[str, Any]],
        runtime_test_result: Optional[Dict[str, Any]] = None,
        verification_results: Optional[List[Dict[str, Any]]] = None,
    ) -> FinalReviewReport:
        """
        Synthesize a FinalReviewReport from specialist findings.

        Steps:
        1. Parse raw_findings dicts into Finding objects for validation.
        2. Compute deterministic fields (files_reviewed, overall_risk, metadata).
        3. Invoke LLM for deduplication, summary, recommendations.
        4. Re-validate LLM output findings (same model, no hallucination).
        5. Assemble the final report.
        """
        logger.info("synthesizer: started, raw_findings=%d", len(raw_findings))

        # 1. Parse and validate incoming findings
        findings: List[Finding] = []
        for raw in raw_findings:
            try:
                if isinstance(raw, dict):
                    findings.append(Finding(**raw))
                elif isinstance(raw, Finding):
                    findings.append(raw)
            except Exception as exc:
                logger.warning("synthesizer: skipping malformed finding: %s", exc)

        # 2. Deterministic fields (never delegated to LLM)
        files_reviewed = extract_files_reviewed(diff_summary, context, findings)
        overall_risk = compute_overall_risk(findings)
        metadata = build_analysis_metadata(findings)
        
        verification_results_dicts = verification_results or []
        runtime_summary = build_runtime_summary(runtime_test_result)
        verification_summary = build_verification_summary(verification_results_dicts)
        
        verif_objects = []
        for v in verification_results_dicts:
            try:
                verif_objects.append(VerificationResult(**v))
            except Exception:
                pass

        # 3. Handle no-findings case without LLM call
        if not findings:
            logger.info("synthesizer: no findings, short-circuiting LLM call")
            return FinalReviewReport(
                summary="No actionable issues were identified in the reviewed changes.",
                overall_risk="none",
                findings=[],
                recommendations=[],
                files_reviewed=files_reviewed,
                analysis_metadata=metadata,
                runtime_summary=runtime_summary,
                verification_summary=verification_summary,
                verification_results=verif_objects,
            )

        # 4. Build messages and invoke LLM for deduplication + prose
        messages = build_synthesizer_messages(
            review_request=review_request,
            review_plan=review_plan,
            diff_summary=diff_summary,
            context=context,
            findings=[f.model_dump() for f in findings],
            files_reviewed=files_reviewed,
            runtime_summary=runtime_summary.model_dump() if runtime_summary else None,
            verification_summary=verification_summary.model_dump(),
            verification_results=verification_results_dicts,
        )

        llm_output: _SynthesizerLLMOutput = self.provider.structured_invoke(
            messages, _SynthesizerLLMOutput
        )
        logger.info(
            "synthesizer: LLM returned %d consolidated findings",
            len(llm_output.findings),
        )

        # 5. Recompute overall_risk from LLM-consolidated findings
        #    (deduplication may reduce count, but risk only goes down or stays)
        final_findings = llm_output.findings if llm_output.findings else findings
        final_risk = compute_overall_risk(final_findings)
        final_metadata = build_analysis_metadata(final_findings)

        report = FinalReviewReport(
            summary=llm_output.summary,
            overall_risk=final_risk,
            findings=final_findings,
            recommendations=llm_output.recommendations,
            files_reviewed=files_reviewed,
            analysis_metadata=final_metadata,
            runtime_summary=runtime_summary,
            verification_summary=verification_summary,
            verification_results=verif_objects,
        )

        logger.info(
            "synthesizer: completed, overall_risk=%s, findings=%d",
            report.overall_risk,
            len(report.findings),
        )
        return report
