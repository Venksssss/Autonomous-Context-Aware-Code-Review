from typing import List, Optional, Literal
from pydantic import BaseModel


class RepoAnalyzeRequest(BaseModel):
    repository_path: str


class RepoContextRequest(BaseModel):
    repository_path: str
    symbol: str


class Relationship(BaseModel):
    relationship_type: Literal["imports", "calls", "defines"]
    source_file: str
    target_file: Optional[str] = None
    source_symbol: Optional[str] = None
    target_symbol: Optional[str] = None
    source_line: Optional[int] = None
    resolution_status: Literal["resolved", "unresolved", "ambiguous"]


class ResolvedSymbol(BaseModel):
    id: str
    name: str
    qualified_name: str
    symbol_type: str
    file_path: str
    start_line: int
    end_line: int
    start_column: int
    end_column: int
    parent: Optional[str] = None
    parameters: Optional[List[str]] = None


class UnresolvedReference(BaseModel):
    file_path: str
    name: str
    line: int
    kind: str
    resolution_status: Literal["resolved", "unresolved", "ambiguous"]


class RepositoryGraph(BaseModel):
    repository_path: str
    files_analyzed: int
    symbols_count: int
    relationships_count: int
    files: List[str]
    symbols: List[ResolvedSymbol]
    relationships: List[Relationship]
    unresolved_references: List[UnresolvedReference]


class ContextDefinition(BaseModel):
    file: str
    start_line: int
    end_line: int


class ContextCall(BaseModel):
    symbol: str
    file: str
    line: int


class ContextImport(BaseModel):
    module: str
    name: Optional[str] = None
    file: str
    line: int


class SymbolContext(BaseModel):
    symbol: str
    definition: Optional[ContextDefinition] = None
    calls: List[ContextCall]
    called_by: List[ContextCall]
    imports: List[ContextImport]
    imported_by: List[ContextImport]
