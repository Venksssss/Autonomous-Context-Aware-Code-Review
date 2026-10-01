"""
ReviewWorkflowService — application-facing interface to the LangGraph pipeline.

Design rules:
  - Routes call this service, NOT LangGraph directly.
  - This service calls GitService directly (not via HTTP) to retrieve diffs.
  - The LangGraph graph is built with an injected provider for testability.

Why not call the /diff HTTP endpoint internally?
  HTTP round-trips through our own server add latency and create tight
  coupling.  Calling GitService.get_diff() directly is faster, simpler,
  and avoids dependency on a running server during tests.
"""
from __future__ import annotations

import logging
from typing import Optional

from app.agents.graph import build_review_graph
from app.agents.state import ReviewWorkflowState
from app.schemas.review_planner import ReviewPlan
from app.schemas.review_workflow import ReviewWorkflowResult
from app.services.llm.interface import LLMProvider

logger = logging.getLogger(__name__)


class ReviewWorkflowService:
    def __init__(self, provider: Optional[LLMProvider] = None):
        # Accept an injected provider so tests can use FakeLLMProvider
        # without touching global configuration or environment variables.
        self._provider = provider

    def run(
        self,
        review_request: str,
        repository_path: Optional[str] = None,
        base_revision: Optional[str] = None,
        head_revision: Optional[str] = None,
    ) -> ReviewWorkflowResult:
        logger.info("workflow_started: request=%r repo=%r", review_request, repository_path)

        # 1. Optionally fetch diff from GitService (direct call, no HTTP)
        diff_data: Optional[dict] = None
        if repository_path and base_revision and head_revision:
            try:
                from app.services.git_service import GitService, GitAppError
                diff_data = GitService.get_diff(
                    path=repository_path,
                    base_revision=base_revision,
                    head_revision=head_revision,
                )
                logger.info(
                    "workflow: diff retrieved — %d file(s) changed",
                    diff_data.get("total_files_changed", 0),
                )
            except Exception as exc:
                logger.warning("workflow: could not retrieve diff: %s", exc)
                return ReviewWorkflowResult(
                    status="failed",
                    errors=[f"Could not retrieve diff: {exc}"],
                )

        # 2. Build initial state
        initial_state: ReviewWorkflowState = {
            "review_request": review_request,
            "repository_path": repository_path,
            "base_revision": base_revision,
            "head_revision": head_revision,
            "diff": diff_data,
            "review_plan": None,
            "context": None,
            "findings": [],
            "errors": [],
        }

        # 3. Build and run graph
        try:
            graph = build_review_graph(provider=self._provider)
            logger.info("workflow: invoking LangGraph")
            final_state: ReviewWorkflowState = graph.invoke(initial_state)
            logger.info("workflow_completed")
        except Exception as exc:
            msg = f"Workflow execution failed: {exc}"
            logger.error(msg)
            return ReviewWorkflowResult(status="failed", errors=[msg])

        # 4. Assemble result
        errors = final_state.get("errors") or []
        raw_plan = final_state.get("review_plan")

        if raw_plan and not errors:
            try:
                plan = ReviewPlan(**raw_plan)
                return ReviewWorkflowResult(status="planned", review_plan=plan, errors=[])
            except Exception as exc:
                return ReviewWorkflowResult(
                    status="failed",
                    errors=[f"ReviewPlan schema validation failed: {exc}"],
                )

        return ReviewWorkflowResult(
            status="failed" if errors else "planned",
            review_plan=ReviewPlan(**raw_plan) if raw_plan else None,
            errors=errors,
        )
