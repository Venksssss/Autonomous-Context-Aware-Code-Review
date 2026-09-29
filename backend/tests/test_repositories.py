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

@pytest.fixture
def diff_git_repo():
    temp_dir = tempfile.mkdtemp()
    subprocess.run(["git", "init", "-b", "main"], cwd=temp_dir, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=temp_dir, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=temp_dir, capture_output=True)
    
    file_mod = Path(temp_dir) / "mod.txt"
    file_mod.write_text("hello\n")
    
    file_del = Path(temp_dir) / "del.txt"
    file_del.write_text("will be deleted\n")
    
    file_ren = Path(temp_dir) / "old.txt"
    file_ren.write_text("will be renamed\n")
    
    subprocess.run(["git", "add", "."], cwd=temp_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Commit A"], cwd=temp_dir, capture_output=True)
    
    file_mod.write_text("hello world\n") # modified
    
    file_add = Path(temp_dir) / "add.txt"
    file_add.write_text("new file\n") # added
    
    subprocess.run(["git", "rm", "del.txt"], cwd=temp_dir, capture_output=True) # deleted
    subprocess.run(["git", "mv", "old.txt", "new.txt"], cwd=temp_dir, capture_output=True) # renamed
    
    file_bin = Path(temp_dir) / "image.bin"
    file_bin.write_bytes(b'\x00\x01\x02\x03\x04\x05\x06')
    
    subprocess.run(["git", "add", "."], cwd=temp_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Commit B"], cwd=temp_dir, capture_output=True)
    
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_diff_modified_file(diff_git_repo):
    response = client.post("/api/repositories/diff", json={
        "repository_path": diff_git_repo,
        "base_revision": "HEAD~1",
        "head_revision": "HEAD"
    })
    assert response.status_code == 200
    data = response.json()
    files = data["files"]
    
    mod_file = next(f for f in files if f["path"] == "mod.txt")
    assert mod_file["change_type"] == "modified"
    assert mod_file["additions"] == 1
    assert mod_file["deletions"] == 1
    assert "+hello world" in mod_file["patch"]

def test_diff_added_file(diff_git_repo):
    response = client.post("/api/repositories/diff", json={
        "repository_path": diff_git_repo,
        "base_revision": "HEAD~1",
        "head_revision": "HEAD"
    })
    data = response.json()
    add_file = next(f for f in data["files"] if f["path"] == "add.txt")
    assert add_file["change_type"] == "added"
    assert add_file["additions"] == 1
    assert add_file["deletions"] == 0

def test_diff_deleted_file(diff_git_repo):
    response = client.post("/api/repositories/diff", json={
        "repository_path": diff_git_repo,
        "base_revision": "HEAD~1",
        "head_revision": "HEAD"
    })
    data = response.json()
    del_file = next(f for f in data["files"] if f["path"] == "del.txt")
    assert del_file["change_type"] == "deleted"
    assert del_file["additions"] == 0
    assert del_file["deletions"] == 1

def test_diff_multiple_changed_files(diff_git_repo):
    response = client.post("/api/repositories/diff", json={
        "repository_path": diff_git_repo,
        "base_revision": "HEAD~1",
        "head_revision": "HEAD"
    })
    data = response.json()
    assert data["files_changed"] == 5

def test_diff_no_changes(diff_git_repo):
    response = client.post("/api/repositories/diff", json={
        "repository_path": diff_git_repo,
        "base_revision": "HEAD",
        "head_revision": "HEAD"
    })
    data = response.json()
    assert data["files_changed"] == 0
    assert len(data["files"]) == 0

def test_diff_invalid_base_revision(diff_git_repo):
    response = client.post("/api/repositories/diff", json={
        "repository_path": diff_git_repo,
        "base_revision": "invalid_ref_123",
        "head_revision": "HEAD"
    })
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_BASE_REVISION"

def test_diff_invalid_head_revision(diff_git_repo):
    response = client.post("/api/repositories/diff", json={
        "repository_path": diff_git_repo,
        "base_revision": "HEAD",
        "head_revision": "invalid_ref_123"
    })
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_HEAD_REVISION"

def test_diff_renamed_file(diff_git_repo):
    response = client.post("/api/repositories/diff", json={
        "repository_path": diff_git_repo,
        "base_revision": "HEAD~1",
        "head_revision": "HEAD"
    })
    data = response.json()
    renamed_file = next(f for f in data["files"] if f["path"] in ("new.txt", "old.txt") and f["change_type"] == "renamed")
    assert renamed_file is not None
    assert renamed_file["change_type"] == "renamed"

def test_diff_fastapi_integration(diff_git_repo):
    response = client.post("/api/repositories/diff", json={
        "repository_path": diff_git_repo,
        "base_revision": "HEAD~1",
        "head_revision": "HEAD"
    })
    assert response.status_code == 200
    data = response.json()
    assert "repository" in data
    assert "base_revision" in data
    assert "head_revision" in data
    assert data["files_changed"] == 5
    assert isinstance(data["files"], list)

def test_diff_binary_file(diff_git_repo):
    response = client.post("/api/repositories/diff", json={
        "repository_path": diff_git_repo,
        "base_revision": "HEAD~1",
        "head_revision": "HEAD"
    })
    data = response.json()
    bin_file = next(f for f in data["files"] if f["path"] == "image.bin")
    assert bin_file["change_type"] == "added"
    assert bin_file["patch"] is None
    assert bin_file["additions"] == 0
    assert bin_file["deletions"] == 0
