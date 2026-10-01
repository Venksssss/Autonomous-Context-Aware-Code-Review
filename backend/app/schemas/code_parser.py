from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Segment 1 — Parse schemas
# ---------------------------------------------------------------------------

class ParseRequest(BaseModel):
    """Request model for single-file code parsing."""
    repository_path: str
    file_path: str


class ParseResponse(BaseModel):
    """Response model representing a Tree-sitter parse result."""
    path: str
    language: str
    parsed: bool
    has_errors: bool
    root_node_type: Optional[str] = None
    error_count: int = 0


# ---------------------------------------------------------------------------
# Segment 2 — Analysis schemas
# ---------------------------------------------------------------------------

class SymbolType(str, Enum):
    """Enumeration of extractable Python code symbol types."""
    module = "module"
    class_ = "class"
    function = "function"
    method = "method"


class Symbol(BaseModel):
    """A named code symbol extracted from a source file."""
    name: str
    qualified_name: str
    symbol_type: SymbolType
    file_path: str
    start_line: int           # 1-based
    end_line: int             # 1-based
    start_column: int         # 0-based (matches editor conventions)
    end_column: int
    parent: Optional[str] = None
    parameters: Optional[List[str]] = None


class Import(BaseModel):
    """A single import statement extracted from a source file."""
    module: str
    name: Optional[str] = None    # populated for `from X import Y`
    alias: Optional[str] = None   # populated for `import X as Y`
    line: int                     # 1-based


class CallSite(BaseModel):
    """A function or method call site found in a source file."""
    name: str          # e.g. "verify_token" or "service.process"
    line: int          # 1-based
    column: int        # 0-based
    kind: str = "call"


class AnalyzeRequest(BaseModel):
    """Request model for code analysis (symbol + import + call extraction)."""
    repository_path: str
    file_path: str


class FileAnalysis(BaseModel):
    """Complete structured analysis of a single source file."""
    file_path: str
    language: str
    symbols: List[Symbol]
    imports: List[Import]
    calls: List[CallSite]
    has_errors: bool
    error_count: int
