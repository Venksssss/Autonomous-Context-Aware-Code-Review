from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from app.schemas.repository import RepositoryInspectResponse, DiffRequest, DiffResponse
from app.services.git_service import GitService, GitServiceError, GitAppError

router = APIRouter()

@router.get("/inspect", response_model=RepositoryInspectResponse)
def inspect_repository(repository_path: str = Query(..., description="Path to the repository to inspect")):
    try:
        result = GitService.inspect_repository(repository_path)
        return RepositoryInspectResponse(**result)
    except GitServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="An unexpected internal error occurred")

@router.post("/diff", response_model=DiffResponse)
def get_diff(request: DiffRequest):
    try:
        result = GitService.get_diff(
            path=request.repository_path,
            base_revision=request.base_revision,
            head_revision=request.head_revision
        )
        return DiffResponse(**result)
    except GitAppError as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": e.code, "message": e.message}}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected internal error occurred."}}
        )
