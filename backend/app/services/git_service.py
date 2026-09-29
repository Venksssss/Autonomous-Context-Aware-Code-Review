import os
import subprocess
from pathlib import Path

class GitServiceError(Exception):
    pass

class GitAppError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(self.message)

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

    @staticmethod
    def get_diff(path: str, base_revision: str, head_revision: str) -> dict:
        target_path = Path(path)
        
        if not target_path.exists() or not target_path.is_dir():
            raise GitAppError("INVALID_REPOSITORY", "The specified repository path is invalid or not a directory.")
            
        try:
            subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"],
                cwd=target_path, capture_output=True, text=True, check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise GitAppError("INVALID_REPOSITORY", "The specified path is not a valid Git repository.")

        for rev, code in [(base_revision, "INVALID_BASE_REVISION"), (head_revision, "INVALID_HEAD_REVISION")]:
            try:
                subprocess.run(["git", "rev-parse", "--verify", rev], cwd=target_path, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError:
                raise GitAppError(code, f"The specified revision could not be resolved: {rev}")

        base_sha = subprocess.run(["git", "rev-parse", "--verify", base_revision], cwd=target_path, capture_output=True, text=True).stdout.strip()
        head_sha = subprocess.run(["git", "rev-parse", "--verify", head_revision], cwd=target_path, capture_output=True, text=True).stdout.strip()
        
        if base_sha == head_sha:
            return {
                "repository": str(target_path.absolute()),
                "base_revision": base_revision,
                "head_revision": head_revision,
                "files_changed": 0,
                "files": []
            }

        try:
            status_result = subprocess.run(
                ["git", "diff", "-M", "--name-status", f"{base_sha}..{head_sha}"],
                cwd=target_path, capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError:
            raise GitAppError("GIT_DIFF_FAILED", "Failed to generate Git diff.")

        status_lines = status_result.stdout.strip().split("\n")
        changed_files = []
        
        for line in status_lines:
            if not line: continue
            parts = line.split("\t")
            code_str = parts[0]
            status_char = code_str[0].upper()
            
            old_path = None
            new_path = None
            
            if status_char in ('R', 'C'):
                if len(parts) >= 3:
                    old_path = parts[1]
                    new_path = parts[2]
                else:
                    new_path = parts[1]
            else:
                new_path = parts[1]
                
            change_type = "unknown"
            if status_char == 'A': change_type = "added"
            elif status_char == 'M': change_type = "modified"
            elif status_char == 'D': change_type = "deleted"
            elif status_char == 'R': change_type = "renamed"
            elif status_char == 'C': change_type = "copied"

            patch = None
            additions = 0
            deletions = 0
            
            paths_to_diff = []
            if old_path and new_path:
                paths_to_diff = [old_path, new_path]
            elif new_path:
                paths_to_diff = [new_path]
                
            diff_cmd = ["git", "diff", "-M", f"{base_sha}..{head_sha}", "--"] + paths_to_diff
            patch_result = subprocess.run(diff_cmd, cwd=target_path, capture_output=True, text=True)
            patch_text = patch_result.stdout
            
            if "Binary files " in patch_text and " differ" in patch_text:
                patch = None
            else:
                if patch_text.strip():
                    patch = patch_text
                    
            numstat_cmd = ["git", "diff", "-M", "--numstat", f"{base_sha}..{head_sha}", "--"] + paths_to_diff
            numstat_result = subprocess.run(numstat_cmd, cwd=target_path, capture_output=True, text=True)
            numstat_lines = numstat_result.stdout.strip().split("\n")
            
            for numstat_line in numstat_lines:
                if numstat_line:
                    n_parts = numstat_line.split("\t")
                    if len(n_parts) >= 2:
                        try:
                            additions += int(n_parts[0]) if n_parts[0] != '-' else 0
                            deletions += int(n_parts[1]) if n_parts[1] != '-' else 0
                        except ValueError:
                            pass
                            
            changed_files.append({
                "path": new_path if new_path else old_path,
                "change_type": change_type,
                "additions": additions,
                "deletions": deletions,
                "patch": patch
            })

        return {
            "repository": str(target_path.absolute()),
            "base_revision": base_revision,
            "head_revision": head_revision,
            "files_changed": len(changed_files),
            "files": changed_files
        }
