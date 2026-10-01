"""
Planner node — first node in the review workflow graph.

Reads the review request and available diff context from shared state,
calls ReviewPlannerService (which uses the injected LLM provider),
and writes the resulting ReviewPlan back into state as a plain dict.

Why ReviewPlannerService and not ChatOllama directly?
  The node must not depend on a specific LLM vendor.  The provider
  abstraction (LLMFactory → OllamaProvider / FakeLLMProvider) sits
  below ReviewPlannerService, so swapping providers is transparent here.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.agents.state import ReviewWorkflowState
from app.services.llm.interface import LLMProvider
from app.services.review_planner import ReviewPlannerService

logger = logging.getLogger(__name__)


def build_context_summary(state: ReviewWorkflowState) -> Optional[Dict[str, Any]]:
    """
    Build a concise, prompt-safe summary of repository change information
    from the state diff.  We do NOT dump the entire diff; only the fields
    the planner needs to decide scope and priority.
    """
    diff = state.get("diff")
    if not diff:
        return None

    changed_files = [f.get("file_path") for f in diff.get("changed_files", [])]
    summary: Dict[str, Any] = {
        "changed_files": changed_files,
        "total_additions": diff.get("total_additions", 0),
        "total_deletions": diff.get("total_deletions", 0),
    }
    # Include the first meaningful patch text per file (truncated) so the
    # planner has some signal without being swamped by large diffs.
    patches = []
    for cf in diff.get("changed_files", [])[:5]:          # cap at 5 files
        patch = cf.get("patch", "")
        if patch:
            patches.append({"file": cf.get("file_path"), "patch": patch[:800]})
    if patches:
        summary["patches"] = patches
    return summary


def planner_node(state: ReviewWorkflowState, provider: Optional[LLMProvider] = None) -> ReviewWorkflowState:
    """
    LangGraph node — orchestrates the AI review planner.

    Returns a partial state dict; LangGraph merges it with the existing state.
    """
    logger.info("planner_node: started")

    try:
        service = ReviewPlannerService(provider=provider)
        context_summary = build_context_summary(state)
        plan = service.generate_plan(
            request=state.get("review_request", ""),
            repository_context=context_summary,
        )
        logger.info("planner_node: completed")
        return {
            "review_plan": plan.model_dump(),
            "errors": [],
        }
    except Exception as exc:
        msg = f"planner_node failed: {exc}"
        logger.error(msg)
        return {
            "review_plan": None,
            "errors": [msg],
        }
