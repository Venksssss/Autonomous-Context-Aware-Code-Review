from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class SymbolContext(BaseModel):
    file_path: str
    symbol_name: str
    kind: str
    definitions: List[Dict[str, Any]] = []
    calls: List[Dict[str, Any]] = []
    called_by: List[Dict[str, Any]] = []
    imports: List[Dict[str, Any]] = []
    imported_by: List[Dict[str, Any]] = []
    source_snippet: Optional[str] = None

class RepositoryContext(BaseModel):
    changed_files: List[str]
    changed_symbols: List[str]
    symbols_context: List[SymbolContext]
    related_files: List[str] = []
