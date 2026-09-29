import pytest
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.fixture
def parser_repo():
    temp_dir = tempfile.mkdtemp()
    repo_path = Path(temp_dir)
    
    # 1. Valid python file
    valid_py = repo_path / "valid.py"
    valid_py.write_text("def hello():\n    print('world')\n")
    
    # 2. Syntax error python file
    error_py = repo_path / "error.py"
    error_py.write_text("def hello() print('world')\n") # Missing colon
    
    # 3. Empty python file
    empty_py = repo_path / "empty.py"
    empty_py.write_text("")
    
    # 4. Unsupported extension
    unsupported = repo_path / "style.css"
    unsupported.write_text("body { color: red; }")
    
    yield str(repo_path)
    shutil.rmtree(temp_dir, ignore_errors=True)

def test_parse_valid_python(parser_repo):
    response = client.post("/api/code/parse", json={
        "repository_path": parser_repo,
        "file_path": "valid.py"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["path"] == "valid.py"
    assert data["language"] == "python"
    assert data["parsed"] is True
    assert data["has_errors"] is False
    assert data["root_node_type"] == "module"
    assert data["error_count"] == 0

def test_parse_syntax_error(parser_repo):
    response = client.post("/api/code/parse", json={
        "repository_path": parser_repo,
        "file_path": "error.py"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["path"] == "error.py"
    assert data["language"] == "python"
    assert data["parsed"] is True
    assert data["has_errors"] is True
    assert data["error_count"] > 0
    assert data["root_node_type"] == "module"

def test_parse_empty_python(parser_repo):
    response = client.post("/api/code/parse", json={
        "repository_path": parser_repo,
        "file_path": "empty.py"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "python"
    assert data["parsed"] is True
    assert data["has_errors"] is False
    assert data["root_node_type"] == "module"
    assert data["error_count"] == 0

def test_parse_unsupported_extension(parser_repo):
    response = client.post("/api/code/parse", json={
        "repository_path": parser_repo,
        "file_path": "style.css"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["language"] == "unsupported"
    assert data["parsed"] is False

def test_parse_nonexistent_file(parser_repo):
    response = client.post("/api/code/parse", json={
        "repository_path": parser_repo,
        "file_path": "does_not_exist.py"
    })
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "FILE_NOT_FOUND"

def test_parse_path_traversal(parser_repo):
    response = client.post("/api/code/parse", json={
        "repository_path": parser_repo,
        "file_path": "../secret.txt"
    })
    assert response.status_code == 400
    assert response.json()["error"]["code"] in ["PATH_TRAVERSAL_DETECTED", "FILE_NOT_FOUND"] 
    # Can be FILE_NOT_FOUND if traversal check fails or file actually doesn't exist out of bounds, but our logic checks bounds first

def test_parse_invalid_repository():
    response = client.post("/api/code/parse", json={
        "repository_path": "/invalid/repo/123",
        "file_path": "test.py"
    })
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REPOSITORY"
