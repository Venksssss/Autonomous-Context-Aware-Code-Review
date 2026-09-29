from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.schemas.code_parser import ParseRequest, ParseResponse
from app.services.code_parser import CodeParserService, CodeParserError

router = APIRouter()

@router.post("/parse", response_model=ParseResponse)
def parse_code(request: ParseRequest):
    """
    Parses a single source code file into a syntax tree and returns structural metadata.
    """
    try:
        result = CodeParserService.parse_file(
            repository_path=request.repository_path,
            file_path=request.file_path
        )
        return ParseResponse(**result)
    except CodeParserError as e:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": e.code, "message": e.message}}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected internal error occurred."}}
        )
