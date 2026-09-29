from pydantic import BaseModel

class RepositoryInspectResponse(BaseModel):
    repository_path: str
    repository_root: str
    current_branch: str
    current_commit: str
    is_git_repository: bool
