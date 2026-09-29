from fastapi import APIRouter, HTTPException, Query
from app.schemas.repository import RepositoryInspectResponse
from app.services.git_service import GitService, GitServiceError

router = APIRouter()

@router.get("/inspect", response_model=RepositoryInspectResponse)
def inspect_repository(repository_path: str = Query(..., description="Path to the repository to inspect")):
    try:
        result = GitService.inspect_repository(repository_path)
        return RepositoryInspectResponse(**result)
    except GitServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Avoid exposing internal stack traces, log it in a real app
        raise HTTPException(status_code=500, detail="An unexpected internal error occurred")
