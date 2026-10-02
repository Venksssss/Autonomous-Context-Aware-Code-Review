import os
import glob
from pathlib import Path
from typing import List, Optional
from app.schemas.test_run import TestDiscoveryResult, DiscoveredTest

class TestDiscoveryError(Exception):
    pass

class TestDiscoveryService:
    def discover_tests(self, repository_path: str) -> TestDiscoveryResult:
        repo_path = Path(repository_path).resolve()
        
        if not repo_path.exists() or not repo_path.is_dir():
            raise TestDiscoveryError("TEST_TARGET_INVALID")

        # Basic security: ensure it's not a root dir or similar (though handled primarily by route)
        
        discovered: List[DiscoveredTest] = []
        
        # Check for pytest configuration or common test directories
        # We assume pytest for now if we find test files
        
        # Avoid recursion into ignored directories
        ignored_dirs = {".git", ".venv", "venv", "__pycache__", "node_modules"}
        
        for root, dirs, files in os.walk(repo_path):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in ignored_dirs]
            
            # Check for `tests/` or `test/` directory itself
            rel_root = Path(root).relative_to(repo_path)
            
            for file in files:
                if (file.startswith("test_") and file.endswith(".py")) or (file.endswith("_test.py")):
                    rel_path = (rel_root / file).as_posix()
                    discovered.append(
                        DiscoveredTest(
                            path=rel_path,
                            framework="pytest",
                            kind="test_file"
                        )
                    )
        
        # Sort for deterministic output
        discovered.sort(key=lambda x: x.path)
        
        framework = "pytest" if discovered else None
        
        return TestDiscoveryResult(
            framework=framework,
            tests=discovered,
            test_count=len(discovered)
        )
