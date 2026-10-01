from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.schemas.code_parser import (
    AnalyzeRequest,
    FileAnalysis,
    ParseRequest,
    ParseResponse,
)
from app.services.code_analyzer import CodeAnalyzerService
from app.services.code_parser import CodeParserError, CodeParserService

router = APIRouter()


@router.post("/parse", response_model=ParseResponse)
def parse_code(request: ParseRequest):
    """
    Parse a single source code file into a syntax tree and return structural metadata.
    """
    try:
        result = CodeParserService.parse_file(
            repository_path=request.repository_path,
            file_path=request.file_path,
        )
        return ParseResponse(**result)
    except CodeParserError as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": e.code, "message": e.message}},
        )
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected internal error occurred."}},
        )


@router.post("/analyze", response_model=FileAnalysis)
def analyze_code(request: AnalyzeRequest):
    """
    Extract structured symbols, imports, and call sites from a source file using Tree-sitter.

    Returns a FileAnalysis containing:
    - **symbols**: classes, functions, methods (with qualified names and source locations)
    - **imports**: import and from-import statements
    - **calls**: function/method call sites
    - **has_errors** / **error_count**: parse-error metadata
    """
    try:
        result = CodeAnalyzerService.analyze_file(
            repository_path=request.repository_path,
            file_path=request.file_path,
        )
        return result
    except CodeParserError as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": e.code, "message": e.message}},
        )
    except Exception:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected internal error occurred."}},
        )
