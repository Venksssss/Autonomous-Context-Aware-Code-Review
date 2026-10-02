from typing import Dict, Any, Optional
from app.agents.state import ReviewWorkflowState
from app.services.test_service import TestService
from app.schemas.test_run import TestExecutionRequest
from app.config import settings

def test_execution_node(state: ReviewWorkflowState) -> Dict[str, Any]:
    """
    Executes tests against the repository and stores the runtime result in state.
    Uses Docker execution by default if enabled, otherwise falls back to local.
    """
    repo_path = state.get("repository_path")
    if not repo_path:
        return {}
        
    execution_mode = "docker" if settings.docker_sandbox_enabled else "local"
    
    # If Docker is requested but unavailable, the service will raise an exception.
    # In that case, we can catch it and record the error, but we want the workflow
    # to continue (verification will just mark it as not_tested).
    try:
        request = TestExecutionRequest(
            repository_path=repo_path,
            execution_mode=execution_mode
        )
        service = TestService()
        result = service.execute_tests(request)
        return {"runtime_test_result": result.model_dump()}
    except Exception as e:
        # Fallback to local if docker is requested but unavailable?
        # The instructions say: "If Docker is unavailable: preserve static findings, append runtime/verification error, continue workflow"
        return {
            "errors": [f"TestExecutionNode failed ({execution_mode}): {str(e)}"]
        }
