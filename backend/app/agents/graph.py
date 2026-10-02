"""
LangGraph review workflow graph.

Graph topology (Phase 3 Segment 4):

    START → planner → context_agent → security_agent ─┐
                                    → quality_agent  ─┤
                                                       ↓
                                                  synthesizer
                                                       ↓
                                                      END

Fan-in pattern: both security_agent and quality_agent feed directly into
synthesizer.  LangGraph's compiled StateGraph with an add-reducer on
`findings` guarantees that synthesizer only starts once BOTH upstream nodes
have returned (because the compiled graph waits for all edges arriving at a
node before executing it).

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
from app.agents.nodes.context_agent import context_agent_node
from app.agents.nodes.security_agent import security_agent_node
from app.agents.nodes.quality_agent import quality_agent_node
from app.agents.nodes.test_execution import test_execution_node
from app.agents.nodes.verification_agent import verification_agent_node
from app.agents.nodes.synthesizer import synthesizer_node
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

    # Bind the provider into LLM-using nodes via functools.partial so the
    # graph itself remains provider-agnostic.
    bound_planner = functools.partial(planner_node, provider=provider)
    bound_security = functools.partial(security_agent_node, provider=provider)
    bound_quality = functools.partial(quality_agent_node, provider=provider)
    bound_verification = functools.partial(verification_agent_node, provider=provider)
    bound_synthesizer = functools.partial(synthesizer_node, provider=provider)

    graph.add_node("planner", bound_planner)
    graph.add_node("context_agent", context_agent_node)
    graph.add_node("security_agent", bound_security)
    graph.add_node("quality_agent", bound_quality)
    graph.add_node("test_execution", test_execution_node)
    graph.add_node("verification_agent", bound_verification)
    graph.add_node("synthesizer", bound_synthesizer)

    # Linear prefix
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "context_agent")

    # Fan-out: context_agent → both specialists
    graph.add_edge("context_agent", "security_agent")
    graph.add_edge("context_agent", "quality_agent")

    # Fan-in: both specialists -> test_execution
    graph.add_edge("security_agent", "test_execution")
    graph.add_edge("quality_agent", "test_execution")
    
    graph.add_edge("test_execution", "verification_agent")
    graph.add_edge("verification_agent", "synthesizer")

    graph.add_edge("synthesizer", END)

    return graph.compile()
