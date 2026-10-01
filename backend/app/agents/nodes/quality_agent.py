import logging
from typing import Optional
from app.agents.state import ReviewWorkflowState
from app.services.llm.interface import LLMProvider
from app.services.review_agents.quality_reviewer import QualityReviewerService
from app.agents.nodes.planner import build_context_summary
from app.agents.nodes.security_agent import validate_finding

logger = logging.getLogger(__name__)

def quality_agent_node(state: ReviewWorkflowState, provider: Optional[LLMProvider] = None) -> ReviewWorkflowState:
    """
    LangGraph node — orchestrates the Quality Reviewer.
    Appends validated findings to the state.
    """
    logger.info("quality_agent: started")
    
    review_plan = state.get("review_plan")
    if review_plan:
        scope = [s.lower() for s in review_plan.get("scope", [])]
        if "quality" not in scope and "logic" not in scope and "performance" not in scope:
            logger.info("quality_agent: skipping, quality/logic not in scope")
            return {"findings": [], "errors": []}
        
    try:
        service = QualityReviewerService(provider=provider)
        
        diff_summary = build_context_summary(state) or {}
        context = state.get("context", {})
        
        agent_findings = service.generate_findings(
            review_request=state.get("review_request", ""),
            diff_summary=diff_summary,
            context=context
        )
        
        valid_findings = []
        for finding in agent_findings.findings:
            if validate_finding(finding, state):
                finding.source_agent = "quality"
                valid_findings.append(finding.model_dump())
                
        logger.info(f"quality_agent: completed, found {len(valid_findings)} findings")
        return {"findings": valid_findings, "errors": []}
        
    except Exception as exc:
        msg = f"quality_agent failed: {exc}"
        logger.error(msg)
        return {"findings": [], "errors": [msg]}
