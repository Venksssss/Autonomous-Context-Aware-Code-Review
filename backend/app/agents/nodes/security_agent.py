import logging
import os
from typing import Optional
from app.agents.state import ReviewWorkflowState
from app.services.llm.interface import LLMProvider
from app.services.review_agents.security_reviewer import SecurityReviewerService
from app.schemas.agent_findings import Finding
from app.agents.nodes.planner import build_context_summary

logger = logging.getLogger(__name__)

def validate_finding(finding: Finding, state: ReviewWorkflowState) -> bool:
    """
    Validates finding evidence. Ensure the LLM didn't hallucinate arbitrary file paths.
    """
    repo_path = state.get("repository_path")
    if not repo_path:
        return True # Can't validate purely synthetic paths
        
    full_path = os.path.join(repo_path, finding.file_path)
    if not os.path.exists(full_path):
        logger.warning(f"Validation failed: file {finding.file_path} does not exist.")
        return False
        
    if finding.start_line is not None and finding.end_line is not None:
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                num_lines = sum(1 for _ in f)
            if not (1 <= finding.start_line <= finding.end_line <= num_lines):
                logger.warning(f"Validation failed: line numbers out of bounds in {finding.file_path}.")
                return False
        except Exception:
            return False
            
    return True

def security_agent_node(state: ReviewWorkflowState, provider: Optional[LLMProvider] = None) -> ReviewWorkflowState:
    """
    LangGraph node — orchestrates the Security Reviewer.
    Appends validated findings to the state.
    """
    logger.info("security_agent: started")
    
    review_plan = state.get("review_plan")
    if review_plan and "security" not in [s.lower() for s in review_plan.get("scope", [])]:
        logger.info("security_agent: skipping, security not in scope")
        return {"findings": [], "errors": []}
        
    try:
        service = SecurityReviewerService(provider=provider)
        
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
                finding.source_agent = "security"
                valid_findings.append(finding.model_dump())
                
        logger.info(f"security_agent: completed, found {len(valid_findings)} findings")
        return {"findings": valid_findings, "errors": []}
        
    except Exception as exc:
        msg = f"security_agent failed: {exc}"
        logger.error(msg)
        return {"findings": [], "errors": [msg]}
