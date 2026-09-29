import os
import subprocess
import tempfile
import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def temp_git_repo():
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    
    # Initialize a git repository
    subprocess.run(["git", "init", "-b", "main"], cwd=temp_dir, capture_output=True)
    
    # Configure git to allow commits
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, capture_output=True, check=True)
    
    # Create a file and commit it so we have a HEAD
    test_file = Path(temp_dir) / "test.txt"
    test_file.write_text("hello world")
    
    subprocess.run(["git", "add", "test.txt"], cwd=temp_dir, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, capture_output=True, check=True)
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def temp_empty_dir():
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_inspect_valid_git_repo(temp_git_repo):
    response = client.get(f"/api/repositories/inspect?repository_path={temp_git_repo}")
    assert response.status_code == 200
    data = response.json()
    
    assert data["is_git_repository"] is True
    assert data["repository_path"] == str(Path(temp_git_repo).absolute())
    assert data["repository_root"].lower() == str(Path(temp_git_repo).absolute()).lower()
    assert data["current_branch"] == "main"
    assert len(data["current_commit"]) in [40, 64]  # SHA-1 or SHA-256 length

def test_inspect_invalid_path():
    invalid_path = "/path/that/definitely/does/not/exist/12345"
    response = client.get(f"/api/repositories/inspect?repository_path={invalid_path}")
    assert response.status_code == 400
    assert "Path does not exist" in response.json()["detail"]

def test_inspect_normal_directory(temp_empty_dir):
    response = client.get(f"/api/repositories/inspect?repository_path={temp_empty_dir}")
    assert response.status_code == 400
    assert "Path is not a Git repository" in response.json()["detail"]
