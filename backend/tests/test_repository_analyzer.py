import pytest
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.services.repository_analyzer import RepositoryAnalyzerService
from app.services.code_parser import CodeParserError

client = TestClient(app)

@pytest.fixture
def repo_fixture():
    tmp = tempfile.mkdtemp()
    repo_path = Path(tmp)
    
    app_dir = repo_path / "app"
    app_dir.mkdir()
    
    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    
    (app_dir / "auth.py").write_text(
        "def verify_token(token):\n"
        "    return token == 'valid'\n",
        encoding="utf-8"
    )
    
    (app_dir / "payment.py").write_text(
        "from app.auth import verify_token\n"
        "\n"
        "class PaymentService:\n"
        "    def process(self, token):\n"
        "        return verify_token(token)\n",
        encoding="utf-8"
    )
    
    (app_dir / "controller.py").write_text(
        "from app.payment import PaymentService\n"
        "\n"
        "def pay(token):\n"
        "    service = PaymentService()\n"
        "    return service.process(token)\n",
        encoding="utf-8"
    )
    
    # Ambiguous test case
    (app_dir / "a.py").write_text("def validate():\n    pass\n", encoding="utf-8")
    (app_dir / "b.py").write_text("def validate():\n    pass\n", encoding="utf-8")
    (app_dir / "ambiguous_caller.py").write_text(
        "def do_work():\n"
        "    validate()\n"
        "    external_library_function()\n",
        encoding="utf-8"
    )

    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)

def test_repository_discovery(repo_fixture):
    files = RepositoryAnalyzerService.discover_python_files(Path(repo_fixture))
    file_strs = [f.as_posix() for f in files]
    assert "app/__init__.py" in file_strs
    assert "app/auth.py" in file_strs
    assert "app/payment.py" in file_strs
    assert "app/controller.py" in file_strs

def test_module_resolution(repo_fixture):
    # Test file-to-module mapping implicitly via the output module strings
    graph = RepositoryAnalyzerService.analyze_repository(repo_fixture)
    # Check that verify_token is known to be in app.auth
    syms = [s for s in graph.symbols if s.name == "verify_token"]
    assert len(syms) == 1
    assert "app.auth" in syms[0].id

def test_import_resolution(repo_fixture):
    graph = RepositoryAnalyzerService.analyze_repository(repo_fixture)
    # verify payment imports auth
    imports = [r for r in graph.relationships if r.relationship_type == "imports"]
    
    auth_import = next(r for r in imports if r.source_file == "app/payment.py")
    assert auth_import.target_file == "app/auth.py"
    assert auth_import.target_symbol == "verify_token"
    assert auth_import.resolution_status == "resolved"
    
    payment_import = next(r for r in imports if r.source_file == "app/controller.py")
    assert payment_import.target_file == "app/payment.py"
    assert payment_import.target_symbol == "PaymentService"
    assert payment_import.resolution_status == "resolved"

def test_call_resolution(repo_fixture):
    graph = RepositoryAnalyzerService.analyze_repository(repo_fixture)
    calls = [r for r in graph.relationships if r.relationship_type == "calls"]
    
    # process -> verify_token
    verify_call = next(r for r in calls if r.source_symbol == "PaymentService.process" and r.target_symbol == "verify_token")
    assert verify_call.target_file == "app/auth.py"
    assert verify_call.resolution_status == "resolved"
    
    # pay -> PaymentService
    pay_call = next(r for r in calls if r.source_symbol == "pay" and r.target_symbol == "PaymentService")
    assert pay_call.target_file == "app/payment.py"
    assert pay_call.resolution_status == "resolved"
    
    # pay -> service.process (Globally unique fallback check since process is unique, or it might be unresolved)
    # Wait, process is globally unique in our fixture (PaymentService.process)
    process_call = next(r for r in calls if r.source_symbol == "pay" and r.target_symbol == "PaymentService.process")
    assert process_call.target_file == "app/payment.py"
    assert process_call.resolution_status == "resolved"

def test_ambiguity(repo_fixture):
    graph = RepositoryAnalyzerService.analyze_repository(repo_fixture)
    # Call to validate in ambiguous_caller.py
    calls = [r for r in graph.relationships if r.relationship_type == "calls" and r.source_file == "app/ambiguous_caller.py"]
    validate_call = next(r for r in calls if r.target_symbol == "validate")
    assert validate_call.resolution_status == "ambiguous"
    
    # Also check unresolved_refs
    unresolved_validate = next(u for u in graph.unresolved_references if u.name == "validate" and u.file_path == "app/ambiguous_caller.py")
    assert unresolved_validate.resolution_status == "ambiguous"

def test_unresolved_call(repo_fixture):
    graph = RepositoryAnalyzerService.analyze_repository(repo_fixture)
    # external_library_function
    unresolved = [u for u in graph.unresolved_references if u.name == "external_library_function"]
    assert len(unresolved) == 1
    assert unresolved[0].resolution_status == "unresolved"

def test_get_symbol_context(repo_fixture):
    ctx = RepositoryAnalyzerService.get_symbol_context(repo_fixture, "PaymentService.process")
    assert ctx.symbol == "PaymentService.process"
    assert ctx.definition.file == "app/payment.py"
    assert len(ctx.calls) == 1
    assert ctx.calls[0].symbol == "verify_token"
    assert len(ctx.called_by) == 1
    assert ctx.called_by[0].symbol == "pay"
    assert len(ctx.imports) == 1
    assert ctx.imports[0].module == "app.auth"
    assert len(ctx.imported_by) == 0

def test_get_unknown_symbol_context(repo_fixture):
    with pytest.raises(CodeParserError) as exc_info:
        RepositoryAnalyzerService.get_symbol_context(repo_fixture, "UnknownSymbol")
    assert exc_info.value.code == "SYMBOL_NOT_FOUND"

def test_api_analyze(repo_fixture):
    resp = client.post("/api/repository/analyze", json={"repository_path": repo_fixture})
    assert resp.status_code == 200
    data = resp.json()
    assert data["files_analyzed"] > 0
    assert data["symbols_count"] > 0
    assert data["relationships_count"] > 0

def test_api_context(repo_fixture):
    resp = client.post("/api/repository/context", json={"repository_path": repo_fixture, "symbol": "PaymentService.process"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["symbol"] == "PaymentService.process"
    assert data["definition"]["file"] == "app/payment.py"

def test_api_invalid_repo():
    resp = client.post("/api/repository/analyze", json={"repository_path": "/invalid/path"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REPOSITORY"
