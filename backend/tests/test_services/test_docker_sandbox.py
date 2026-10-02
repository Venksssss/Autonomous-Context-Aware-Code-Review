import os
import shutil
import tempfile
import pytest
import subprocess
from unittest.mock import patch, MagicMock
from pathlib import Path

from app.schemas.test_run import TestExecutionRequest
from app.services.docker_sandbox import DockerSandboxExecutor, DockerSandboxError
from app.services.docker_runtime import DockerRuntime

@pytest.fixture
def temp_repo():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)

class TestDockerSandboxExecutor:
    @patch("subprocess.run")
    def test_execute_passing_test_mocked(self, mock_run, temp_repo):
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.stdout = "======= 1 passed in 0.1s ======="
        mock_process.stderr = ""
        mock_run.return_value = mock_process
        
        executor = DockerSandboxExecutor()
        req = TestExecutionRequest(repository_path=temp_repo, execution_mode="docker")
        res = executor.execute_tests(req)
        
        assert res.status == "passed"
        assert res.sandboxed is True
        assert res.tests_passed == 1
        
        # Verify docker command structure
        cmd_called = mock_run.call_args[0][0]
        assert cmd_called[0] == "docker"
        assert cmd_called[1] == "run"
        assert "--network" in cmd_called
        assert "none" in cmd_called
        assert "--read-only" in cmd_called
        assert "--cap-drop" in cmd_called
        assert "ALL" in cmd_called

    def test_invalid_repository(self):
        executor = DockerSandboxExecutor()
        req = TestExecutionRequest(repository_path="/nonexistent/path", execution_mode="docker")
        with pytest.raises(DockerSandboxError, match="TEST_TARGET_INVALID"):
            executor.execute_tests(req)

    def test_path_traversal(self, temp_repo):
        executor = DockerSandboxExecutor()
        req = TestExecutionRequest(
            repository_path=temp_repo, 
            test_path="../other_dir",
            execution_mode="docker"
        )
        with pytest.raises(DockerSandboxError, match="TEST_TARGET_OUTSIDE_REPOSITORY"):
            executor.execute_tests(req)

    @patch("subprocess.run")
    def test_timeout_handling(self, mock_run, temp_repo):
        # Mock a timeout exception
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd="docker run ...", 
            timeout=60,
            output="some output",
            stderr="some error"
        )
        
        # We also need to mock the subsequent docker kill call to prevent actual execution
        with patch("subprocess.run", side_effect=[mock_run.side_effect, MagicMock()]):
            executor = DockerSandboxExecutor()
            req = TestExecutionRequest(repository_path=temp_repo, execution_mode="docker")
            res = executor.execute_tests(req)
            
            assert res.status == "timeout"
            assert "timeout" in res.stdout

    @patch("subprocess.run")
    def test_image_not_found(self, mock_run, temp_repo):
        mock_process = MagicMock()
        mock_process.returncode = 125
        mock_process.stderr = "Unable to find image 'python:3.12-slim' locally"
        mock_run.return_value = mock_process
        
        executor = DockerSandboxExecutor()
        req = TestExecutionRequest(repository_path=temp_repo, execution_mode="docker")
        with pytest.raises(DockerSandboxError, match="DOCKER_IMAGE_NOT_AVAILABLE"):
            executor.execute_tests(req)

# Check if docker is available
docker_available = DockerRuntime.check_availability()

# Integration tests - these skip if Docker is not available
skip_docker = pytest.mark.skipif(
    not docker_available, 
    reason="Docker is not available on this host"
)

@skip_docker
class TestDockerSandboxIntegration:
    def test_integration_passing_test(self, temp_repo):
        test_path = os.path.join(temp_repo, "test_ok.py")
        with open(test_path, "w") as f:
            f.write("def test_ok():\n    assert True\n")
            
        executor = DockerSandboxExecutor()
        # Set a short timeout for tests
        executor.timeout = 15
        
        req = TestExecutionRequest(repository_path=temp_repo, execution_mode="docker")
        try:
            res = executor.execute_tests(req)
        except DockerSandboxError as e:
            if "DOCKER_IMAGE_NOT_AVAILABLE" in str(e):
                pytest.fail("Trusted sandbox image not available. Build it with: docker build -t agentic-code-review-sandbox:latest -f docker/sandbox/Dockerfile .")
            raise
            
        assert res.status == "passed"
        assert res.exit_code == 0
        assert res.sandboxed is True
        assert res.tests_passed == 1
        
    def test_integration_failing_test(self, temp_repo):
        test_path = os.path.join(temp_repo, "test_fail.py")
        with open(test_path, "w") as f:
            f.write("def test_fail():\n    assert False\n")
            
        executor = DockerSandboxExecutor()
        executor.timeout = 15
        
        req = TestExecutionRequest(repository_path=temp_repo, execution_mode="docker")
        try:
            res = executor.execute_tests(req)
        except DockerSandboxError as e:
            if "DOCKER_IMAGE_NOT_AVAILABLE" in str(e):
                pytest.fail("Trusted sandbox image not available. Build it with: docker build -t agentic-code-review-sandbox:latest -f docker/sandbox/Dockerfile .")
            raise
            
        assert res.status == "failed"
        assert res.exit_code == 1
        assert res.tests_failed == 1

    def test_integration_read_only_fs(self, temp_repo):
        # Attempt to write to the repository source (which should be read-only)
        test_path = os.path.join(temp_repo, "test_ro.py")
        with open(test_path, "w") as f:
            f.write("""
import os
def test_write_fails():
    try:
        with open('test.txt', 'w') as f:
            f.write('hello')
        assert False, "Should not be able to write"
    except OSError:
        assert True
""")
            
        executor = DockerSandboxExecutor()
        executor.timeout = 15
        
        req = TestExecutionRequest(repository_path=temp_repo, execution_mode="docker")
        try:
            res = executor.execute_tests(req)
        except DockerSandboxError as e:
            if "DOCKER_IMAGE_NOT_AVAILABLE" in str(e):
                pytest.fail("Trusted sandbox image not available. Build it with: docker build -t agentic-code-review-sandbox:latest -f docker/sandbox/Dockerfile .")
            raise
            
        assert res.status == "passed"

    def test_integration_network_isolation(self, temp_repo):
        # Attempt to make a network request
        test_path = os.path.join(temp_repo, "test_net.py")
        with open(test_path, "w") as f:
            f.write("""
import urllib.request
def test_network_fails():
    try:
        urllib.request.urlopen('http://8.8.8.8', timeout=1)
        assert False, "Network should be isolated"
    except Exception:
        assert True
""")
            
        executor = DockerSandboxExecutor()
        executor.timeout = 15
        
        req = TestExecutionRequest(repository_path=temp_repo, execution_mode="docker")
        try:
            res = executor.execute_tests(req)
        except DockerSandboxError as e:
            if "DOCKER_IMAGE_NOT_AVAILABLE" in str(e):
                pytest.fail("Trusted sandbox image not available. Build it with: docker build -t agentic-code-review-sandbox:latest -f docker/sandbox/Dockerfile .")
            raise
            
        assert res.status == "passed"

    def test_integration_timeout(self, temp_repo):
        # Create a test that sleeps
        test_path = os.path.join(temp_repo, "test_sleep.py")
        with open(test_path, "w") as f:
            f.write("import time\ndef test_sleep():\n    time.sleep(10)\n    assert True\n")
            
        executor = DockerSandboxExecutor()
        executor.timeout = 2  # Set very short timeout
        
        req = TestExecutionRequest(repository_path=temp_repo, execution_mode="docker")
        try:
            res = executor.execute_tests(req)
        except DockerSandboxError as e:
            if "DOCKER_IMAGE_NOT_AVAILABLE" in str(e):
                pytest.fail("Trusted sandbox image not available.")
            raise
            
        assert res.status == "timeout"
        assert "terminated after" in res.stdout
