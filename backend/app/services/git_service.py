import os
import subprocess
from pathlib import Path

class GitServiceError(Exception):
    pass

class GitService:
    @staticmethod
    def inspect_repository(path: str) -> dict:
        target_path = Path(path)
        
        if not target_path.exists():
            raise GitServiceError(f"Path does not exist: {path}")
            
        if not target_path.is_dir():
            raise GitServiceError(f"Path is not a directory: {path}")
            
        # Check if it's a git repo
        try:
            subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=target_path,
                capture_output=True,
                text=True,
                check=True
            )
        except subprocess.CalledProcessError:
            raise GitServiceError(f"Path is not a Git repository: {path}")
        except FileNotFoundError:
            raise GitServiceError("Git command not found. Is git installed?")
            
        # Get repo root
        try:
            root_result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=target_path,
                capture_output=True,
                text=True,
                check=True
            )
            repository_root = root_result.stdout.strip()
        except subprocess.CalledProcessError:
            raise GitServiceError("Failed to get repository root")
            
        # Get current branch
        try:
            branch_result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=target_path,
                capture_output=True,
                text=True,
                check=True
            )
            current_branch = branch_result.stdout.strip()
        except subprocess.CalledProcessError:
            current_branch = "" # Might be in detached HEAD state or no commits
            
        # Get current commit
        try:
            commit_result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=target_path,
                capture_output=True,
                text=True,
                check=True
            )
            current_commit = commit_result.stdout.strip()
        except subprocess.CalledProcessError:
            current_commit = "" # Might be a repo with no commits yet

        return {
            "repository_path": str(target_path.absolute()),
            "repository_root": str(Path(repository_root).absolute()) if repository_root else "",
            "current_branch": current_branch,
            "current_commit": current_commit,
            "is_git_repository": True
        }
