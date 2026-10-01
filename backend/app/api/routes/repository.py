from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.repository_analyzer import RepoAnalyzeRequest, RepoContextRequest, RepositoryGraph, SymbolContext
from app.services.repository_analyzer import RepositoryAnalyzerService
from app.services.code_parser import CodeParserError

router = APIRouter()

@router.post("/analyze", response_model=RepositoryGraph)
def analyze_repository(request: RepoAnalyzeRequest):
    try:
        result = RepositoryAnalyzerService.analyze_repository(request.repository_path)
        return result
    except CodeParserError as e:
        return JSONResponse(status_code=400, content={"error": {"code": e.code, "message": e.message}})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected internal error occurred."}})

@router.post("/context", response_model=SymbolContext)
def get_repository_context(request: RepoContextRequest):
    try:
        result = RepositoryAnalyzerService.get_symbol_context(request.repository_path, request.symbol)
        return result
    except CodeParserError as e:
        return JSONResponse(status_code=400, content={"error": {"code": e.code, "message": e.message}})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected internal error occurred."}})
