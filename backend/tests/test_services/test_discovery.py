import os
import shutil
import tempfile
import pytest
from pathlib import Path

from app.services.test_discovery import TestDiscoveryService, TestDiscoveryError

@pytest.fixture
def temp_repo():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)

class TestTestDiscoveryService:
    def test_discover_test_files(self, temp_repo):
        # Create some typical test files
        tests_dir = os.path.join(temp_repo, "tests")
        os.makedirs(tests_dir)
        Path(tests_dir, "test_auth.py").touch()
        Path(tests_dir, "test_api.py").touch()
        Path(tests_dir, "utils.py").touch() # not a test
        
        # Another test format
        Path(temp_repo, "auth_test.py").touch()
        
        # Ignored dir
        venv_dir = os.path.join(temp_repo, ".venv")
        os.makedirs(venv_dir)
        Path(venv_dir, "test_ignored.py").touch()

        service = TestDiscoveryService()
        result = service.discover_tests(temp_repo)
        
        assert result.framework == "pytest"
        assert result.test_count == 3
        
        paths = [t.path for t in result.tests]
        # Paths should be deterministic (sorted)
        expected = sorted(["tests/test_api.py", "tests/test_auth.py", "auth_test.py"])
        assert paths == expected
        
        for t in result.tests:
            assert t.framework == "pytest"
            assert t.kind == "test_file"
            
    def test_no_tests_found(self, temp_repo):
        Path(temp_repo, "main.py").touch()
        
        service = TestDiscoveryService()
        result = service.discover_tests(temp_repo)
        
        assert result.framework is None
        assert result.test_count == 0
        assert len(result.tests) == 0

    def test_invalid_repository(self):
        service = TestDiscoveryService()
        with pytest.raises(TestDiscoveryError, match="TEST_TARGET_INVALID"):
            service.discover_tests("/nonexistent/path/12345")
