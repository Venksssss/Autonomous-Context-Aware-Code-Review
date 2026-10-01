"""
LangGraph review workflow graph.

Current graph topology (simple linear pipeline):

    START → planner → END

Future segments will extend this with specialist nodes:

    START → planner → context_agent → security_agent → quality_agent → synthesizer → END

Why a factory function rather than a module-level singleton?
  build_review_graph() receives an optional LLM provider so tests can
  inject FakeLLMProvider without patching global state.
"""
from __future__ import annotations

import functools
from typing import Optional

from langgraph.graph import StateGraph, START, END

from app.agents.state import ReviewWorkflowState
from app.agents.nodes.planner import planner_node
from app.services.llm.interface import LLMProvider


def build_review_graph(provider: Optional[LLMProvider] = None):
    """
    Construct and compile the review workflow StateGraph.

    Args:
        provider: Optional LLM provider injected for testability.
                  When None the production provider from LLMFactory is used.

    Returns:
        A compiled LangGraph runnable.
    """
    graph = StateGraph(ReviewWorkflowState)

    # Bind the provider into the planner node so the graph itself stays
    # provider-agnostic.  functools.partial keeps the node signature clean.
    bound_planner = functools.partial(planner_node, provider=provider)

    graph.add_node("planner", bound_planner)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", END)

    return graph.compile()
