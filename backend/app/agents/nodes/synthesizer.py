"""
Synthesizer node — final node in the review workflow graph.

Reads all specialist findings from state, calls SynthesizerService,
and writes the final_review into state.

Design rules:
  - Does NOT instantiate a concrete LLM; uses the injected provider.
  - Does NOT perform fresh repository exploration.
  - Runs AFTER both security_agent and quality_agent (fan-in).
  - On failure: logs, appends error, leaves final_review as None
    (specialist findings are NOT discarded).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.agents.state import ReviewWorkflowState
from app.services.llm.interface import LLMProvider
from app.services.review_agents.synthesizer import SynthesizerService
from app.agents.nodes.planner import build_context_summary

logger = logging.getLogger(__name__)


def synthesizer_node(
    state: ReviewWorkflowState,
    provider: Optional[LLMProvider] = None,
) -> ReviewWorkflowState:
    """
    LangGraph node — orchestrates the Synthesizer Agent.

    Returns a partial state update containing only final_review and errors;
    existing findings are preserved unchanged by LangGraph's state merger.
    """
    logger.info("synthesizer: started")

    raw_findings: list = state.get("findings") or []
    review_plan: Optional[Dict[str, Any]] = state.get("review_plan")
    context: Optional[Dict[str, Any]] = state.get("context")
    review_request: str = state.get("review_request", "")

    # Build a bounded diff summary (no raw patch text)
    diff_summary = build_context_summary(state)

    try:
        service = SynthesizerService(provider=provider)
        report = service.synthesize(
            review_request=review_request,
            review_plan=review_plan,
            diff_summary=diff_summary,
            context=context,
            raw_findings=raw_findings,
        )
        logger.info(
            "synthesizer: completed, overall_risk=%s findings=%d",
            report.overall_risk,
            len(report.findings),
        )
        return {
            "final_review": report.model_dump(),
            "errors": [],
        }

    except Exception as exc:
        msg = f"synthesizer failed: {exc}"
        logger.error(msg)
        # Specialist findings are preserved; only final_review is absent.
        return {
            "final_review": None,
            "errors": [msg],
        }
