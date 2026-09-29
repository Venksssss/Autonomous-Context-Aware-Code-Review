from enum import Enum
from typing import List, Optional
from pydantic import BaseModel

class RepositoryInspectResponse(BaseModel):
    repository_path: str
    repository_root: str
    current_branch: str
    current_commit: str
    is_git_repository: bool

class ChangeType(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"
    COPIED = "copied"
    UNKNOWN = "unknown"

class DiffRequest(BaseModel):
    repository_path: str
    base_revision: str
    head_revision: str

class ChangedFile(BaseModel):
    path: str
    change_type: ChangeType
    additions: int
    deletions: int
    patch: Optional[str] = None

class DiffResponse(BaseModel):
    repository: str
    base_revision: str
    head_revision: str
    files_changed: int
    files: List[ChangedFile]
