from pydantic import BaseModel
from typing import Optional

class ParseRequest(BaseModel):
    """Request model for code parsing."""
    repository_path: str
    file_path: str

class ParseResponse(BaseModel):
    """Response model representing a code parsing result."""
    path: str
    language: str
    parsed: bool
    has_errors: bool
    root_node_type: Optional[str] = None
    error_count: int = 0
