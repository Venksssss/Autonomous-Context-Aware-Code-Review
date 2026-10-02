"""
Shared LangGraph workflow state for the autonomous code-review system.

Design principle: State contains DATA only — strings, Pydantic dicts, lists.
No parser objects, no HTTP clients, no model handles, no Tree-sitter nodes.
This keeps state serializable and graph-checkpointable in the future.
"""
from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
import operator


class ReviewWorkflowState(TypedDict, total=False):
    # --- Input fields (set before graph starts) ---
    review_request: str
    repository_path: Optional[str]
    base_revision: Optional[str]
    head_revision: Optional[str]

    # --- Populated by nodes ---
    # Raw diff data (from GitService); stored as a dict, not a Pydantic model,
    # so it stays easily serializable across the graph boundary.
    diff: Optional[Dict[str, Any]]

    # Structured ReviewPlan produced by the Planner node
    review_plan: Optional[Dict[str, Any]]

    # Placeholder for future Context Agent output
    context: Optional[Dict[str, Any]]

    # Placeholder for future specialist agent findings
    findings: Annotated[List[Dict[str, Any]], operator.add]

    # Final consolidated report produced by the Synthesizer Agent.
    # None until the synthesizer node runs successfully.
    final_review: Optional[Dict[str, Any]]

    # Errors accumulated across nodes; using add-reducer so multiple
    # nodes can each append without clobbering each other's entries.
    errors: Annotated[List[str], operator.add]
