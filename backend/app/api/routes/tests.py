from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.schemas.test_run import TestDiscoveryResult, TestExecutionRequest, TestExecutionResult
from app.services.test_service import TestService
from app.services.test_discovery import TestDiscoveryError
from app.services.test_executor import TestExecutionError

router = APIRouter()
test_service = TestService()

class DiscoveryRequest(BaseModel):
    repository_path: str

@router.post("/discover", response_model=TestDiscoveryResult)
def discover_tests(request: DiscoveryRequest):
    try:
        return test_service.discover_tests(request.repository_path)
    except TestDiscoveryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TEST_DISCOVERY_FAILED: {str(e)}")

@router.post("/run", response_model=TestExecutionResult)
def run_tests(request: TestExecutionRequest):
    try:
        return test_service.execute_tests(request)
    except TestExecutionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TEST_EXECUTION_FAILED: {str(e)}")
