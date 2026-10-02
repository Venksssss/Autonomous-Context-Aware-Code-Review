import os
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import app

client = TestClient(app)

@pytest.fixture
def temp_repo():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)

def test_api_discover_tests(temp_repo):
    tests_dir = os.path.join(temp_repo, "tests")
    os.makedirs(tests_dir)
    with open(os.path.join(tests_dir, "test_dummy.py"), "w") as f:
        f.write("def test_ok(): pass\n")
        
    response = client.post("/api/tests/discover", json={"repository_path": temp_repo})
    assert response.status_code == 200
    data = response.json()
    assert data["framework"] == "pytest"
    assert data["test_count"] == 1
    assert len(data["tests"]) == 1
    assert data["tests"][0]["path"] == "tests/test_dummy.py"
    
def test_api_discover_invalid_repo():
    response = client.post("/api/tests/discover", json={"repository_path": "/invalid/repo/123"})
    assert response.status_code == 400
    assert "TEST_TARGET_INVALID" in response.text
    
def test_api_run_tests_success(temp_repo):
    with open(os.path.join(temp_repo, "test_ok.py"), "w") as f:
        f.write("def test_ok(): assert True\n")
        
    response = client.post("/api/tests/run", json={"repository_path": temp_repo})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "passed"
    assert data["exit_code"] == 0
    assert data["tests_run"] == 1
    assert data["tests_passed"] == 1
    
def test_api_run_tests_failed(temp_repo):
    with open(os.path.join(temp_repo, "test_fail.py"), "w") as f:
        f.write("def test_fail(): assert False\n")
        
    response = client.post("/api/tests/run", json={"repository_path": temp_repo})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "failed"
    assert data["exit_code"] == 1
    assert data["tests_run"] == 1
    assert data["tests_failed"] == 1
    
def test_api_run_path_traversal(temp_repo):
    response = client.post("/api/tests/run", json={
        "repository_path": temp_repo,
        "test_path": "../other_dir"
    })
    assert response.status_code == 400
    assert "TEST_TARGET_OUTSIDE_REPOSITORY" in response.text

def test_api_run_tests_docker_disabled(temp_repo):
    with patch("app.services.test_service.settings") as mock_settings:
        mock_settings.docker_sandbox_enabled = False
        response = client.post("/api/tests/run", json={
            "repository_path": temp_repo,
            "execution_mode": "docker"
        })
        assert response.status_code == 400
        assert "DOCKER_SANDBOX_DISABLED" in response.text

def test_api_run_tests_docker_unavailable(temp_repo):
    with patch("app.services.test_service.settings") as mock_settings, \
         patch("app.services.test_service.DockerRuntime.check_availability", return_value=False):
        mock_settings.docker_sandbox_enabled = True
        response = client.post("/api/tests/run", json={
            "repository_path": temp_repo,
            "execution_mode": "docker"
        })
        assert response.status_code == 400
        assert "DOCKER_UNAVAILABLE" in response.text

def test_api_run_tests_docker_success(temp_repo):
    with patch("app.services.test_service.settings") as mock_settings, \
         patch("app.services.test_service.DockerRuntime.check_availability", return_value=True), \
         patch("app.services.test_service.DockerSandboxExecutor.execute_tests") as mock_exec:
        
        mock_settings.docker_sandbox_enabled = True
        
        from app.schemas.test_run import TestExecutionResult
        mock_exec.return_value = TestExecutionResult(
            framework="pytest",
            status="passed",
            exit_code=0,
            duration_seconds=1.5,
            stdout="success",
            stderr="",
            tests_run=1,
            tests_passed=1,
            tests_failed=0,
            tests_skipped=0,
            tests_errors=0,
            execution_mode="docker",
            sandboxed=True
        )
        
        response = client.post("/api/tests/run", json={
            "repository_path": temp_repo,
            "execution_mode": "docker"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["execution_mode"] == "docker"
        assert data["sandboxed"] is True
        assert data["status"] == "passed"
