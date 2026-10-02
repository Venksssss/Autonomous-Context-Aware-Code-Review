from __future__ import annotations

import logging
from typing import Optional

from app.agents.graph import build_review_graph
from app.agents.state import ReviewWorkflowState
from app.schemas.review_planner import ReviewPlan
from app.schemas.review_workflow import ReviewWorkflowResult
from app.schemas.final_review import FinalReviewReport
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
            "final_review": None,
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
        raw_findings = final_state.get("findings") or []
        raw_final_review = final_state.get("final_review")

        from app.schemas.agent_findings import Finding

        plan = None
        if raw_plan:
            try:
                plan = ReviewPlan(**raw_plan)
            except Exception as exc:
                errors.append(f"ReviewPlan schema validation failed: {exc}")

        findings = []
        for raw_f in raw_findings:
            try:
                if isinstance(raw_f, dict):
                    findings.append(Finding(**raw_f))
                else:
                    findings.append(raw_f)
            except Exception as exc:
                errors.append(f"Finding schema validation failed: {exc}")

        final_review = None
        if raw_final_review:
            try:
                if isinstance(raw_final_review, dict):
                    final_review = FinalReviewReport(**raw_final_review)
                elif isinstance(raw_final_review, FinalReviewReport):
                    final_review = raw_final_review
            except Exception as exc:
                errors.append(f"FinalReviewReport schema validation failed: {exc}")

        if errors:
            status = "completed_with_errors" if plan else "failed"
        else:
            if plan and repository_path:
                status = "completed"
            elif plan:
                status = "planned"
            else:
                status = "failed"

        return ReviewWorkflowResult(
            status=status,
            review_plan=plan,
            findings=findings,
            final_review=final_review,
            errors=errors,
        )

