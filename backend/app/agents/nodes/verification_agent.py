import json
from typing import Dict, Any, List, Optional
from app.agents.state import ReviewWorkflowState
from app.services.verification_service import VerificationService
from app.prompts.verification import VERIFICATION_SYSTEM_PROMPT
from app.schemas.verification import VerificationResult
from app.services.llm.interface import LLMProvider
from app.services.llm.factory import create_llm_provider

def verification_agent_node(state: ReviewWorkflowState, provider: Optional[LLMProvider] = None) -> Dict[str, Any]:
    """
    Verification Agent Node.
    Reads findings, runtime test results, and repository context.
    Matches deterministically, then invokes LLM to verify findings if needed.
    """
    findings = state.get("findings", [])
    if not findings:
        return {"verification_results": []}

    test_result_dict = state.get("runtime_test_result")
    
    # We may not have a test result if test discovery or execution failed/skipped.
    # The TestExecutionResult was stored as a dict in the state.
    # Reconstruct it to pass to the service.
    test_result = None
    if test_result_dict:
        from app.schemas.test_run import TestExecutionResult
        try:
            test_result = TestExecutionResult(**test_result_dict)
        except Exception:
            pass

    context = state.get("context", {})
    
    if provider is None:
        provider = create_llm_provider()

    verification_results = []
    
    for finding in findings:
        # Generate baseline deterministic result
        candidate = VerificationService.generate_candidate_result(finding, test_result, context)
        
        # If it's inconclusive but we have supporting tests, we should ask the LLM
        if candidate.verification_status == "inconclusive" and candidate.supporting_tests:
            # Prepare prompt for LLM
            prompt = f"Finding:\n{json.dumps(finding, indent=2)}\n\nCandidate Failures:\n"
            failures = VerificationService.identify_evidence(finding, test_result, context)
            for f in failures:
                prompt += f"- {f.test_path}::{f.test_name} ({f.exception_type}): {f.message}\n"
                
            try:
                # Ask LLM for semantic verification
                from app.schemas.verification import AgentVerificationOutput
                
                # To get a structured output for a single verification, we can just use a simple schema
                # Or reuse AgentVerificationOutput and just pull the first one
                llm_response = provider.invoke_structured(
                    system_prompt=VERIFICATION_SYSTEM_PROMPT,
                    user_prompt=prompt,
                    response_model=VerificationResult
                )
                
                # Update candidate based on LLM response
                candidate.verification_status = llm_response.verification_status
                candidate.explanation = llm_response.explanation
                
            except Exception as e:
                # On LLM failure, keep the inconclusive candidate but add error info
                candidate.explanation += f"\n(LLM Error during semantic verification: {str(e)})"

        verification_results.append(candidate.model_dump())

    return {"verification_results": verification_results}
