"""
Tests for CodeAnalyzerService and POST /api/code/analyze.

All tests use temporary in-memory directories — no real repository files.
"""

from __future__ import annotations

import tempfile
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.code_analyzer import CodeAnalyzerService
from app.services.code_parser import CodeParserError

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def src_repo():
    """Temporary directory acting as a repository with several Python files."""
    tmp = tempfile.mkdtemp()
    p = Path(tmp)

    # 1. Main sample matching the spec in the implementation guide
    (p / "payment.py").write_text(
        "from app.auth import verify_token\n"
        "\n"
        "class PaymentService:\n"
        "\n"
        "    def process(self, user):\n"
        "        token = verify_token(user)\n"
        "        return charge(token)\n"
        "\n"
        "def helper(x):\n"
        "    return x + 1\n",
        encoding="utf-8",
    )

    # 2. File with a top-level function only
    (p / "utils.py").write_text(
        "import os\n"
        "import numpy as np\n"
        "\n"
        "def greet(name, greeting='Hello'):\n"
        "    print(greeting)\n",
        encoding="utf-8",
    )

    # 3. Nested function
    (p / "nested.py").write_text(
        "def outer(a):\n"
        "    def inner(b):\n"
        "        return a + b\n"
        "    return inner\n",
        encoding="utf-8",
    )

    # 4. Nested class
    (p / "nesting.py").write_text(
        "class Outer:\n"
        "    class Inner:\n"
        "        def method(self):\n"
        "            pass\n",
        encoding="utf-8",
    )

    # 5. Syntax-error file
    (p / "broken.py").write_text(
        "def bad( print('oops')\n",
        encoding="utf-8",
    )

    # 6. Empty file
    (p / "empty.py").write_text("", encoding="utf-8")

    # 7. Unsupported extension
    (p / "style.css").write_text("body { color: red; }", encoding="utf-8")

    # 8. Multiple methods
    (p / "multi.py").write_text(
        "class Svc:\n"
        "    def alpha(self, x):\n"
        "        foo(x)\n"
        "    def beta(self, y):\n"
        "        bar(y)\n",
        encoding="utf-8",
    )

    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Unit-level tests (CodeAnalyzerService directly)
# ---------------------------------------------------------------------------

def test_class_extraction(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "payment.py")
    classes = [s for s in result.symbols if s.symbol_type == "class"]
    assert len(classes) == 1
    assert classes[0].name == "PaymentService"
    assert classes[0].qualified_name == "PaymentService"
    assert classes[0].parent is None


def test_method_extraction(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "payment.py")
    methods = [s for s in result.symbols if s.symbol_type == "method"]
    assert len(methods) == 1
    assert methods[0].name == "process"
    assert methods[0].qualified_name == "PaymentService.process"
    assert methods[0].parent == "PaymentService"


def test_function_extraction(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "payment.py")
    funcs = [s for s in result.symbols if s.symbol_type == "function"]
    assert len(funcs) == 1
    assert funcs[0].name == "helper"
    assert funcs[0].qualified_name == "helper"


def test_parameters_method(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "payment.py")
    method = next(s for s in result.symbols if s.name == "process")
    assert method.parameters == ["self", "user"]


def test_parameters_function_with_default(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "utils.py")
    fn = next(s for s in result.symbols if s.name == "greet")
    assert "name" in fn.parameters
    assert "greeting" in fn.parameters


def test_import_plain(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "utils.py")
    plain = [i for i in result.imports if i.module == "os"]
    assert len(plain) == 1
    assert plain[0].name is None
    assert plain[0].alias is None


def test_import_alias(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "utils.py")
    aliased = [i for i in result.imports if i.alias == "np"]
    assert len(aliased) == 1
    assert aliased[0].module == "numpy"


def test_from_import(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "payment.py")
    from_imp = [i for i in result.imports if i.module == "app.auth"]
    assert len(from_imp) == 1
    assert from_imp[0].name == "verify_token"


def test_call_extraction(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "payment.py")
    call_names = [c.name for c in result.calls]
    assert "verify_token" in call_names
    assert "charge" in call_names


def test_nested_function(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "nested.py")
    outer = next(s for s in result.symbols if s.name == "outer")
    inner = next(s for s in result.symbols if s.name == "inner")
    assert outer.symbol_type == "function"
    assert inner.symbol_type == "function"
    assert inner.qualified_name == "outer.inner"
    assert inner.parent == "outer"


def test_nested_class(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "nesting.py")
    names = {s.qualified_name for s in result.symbols}
    assert "Outer" in names
    assert "Outer.Inner" in names
    # method inside nested class
    assert "Outer.Inner.method" in names


def test_multiple_methods(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "multi.py")
    methods = [s for s in result.symbols if s.symbol_type == "method"]
    method_names = {m.name for m in methods}
    assert "alpha" in method_names
    assert "beta" in method_names
    # Both should be qualified under Svc
    for m in methods:
        assert m.qualified_name.startswith("Svc.")


def test_syntax_error_file(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "broken.py")
    assert result.language == "python"
    assert result.has_errors is True
    assert result.error_count > 0


def test_empty_file(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "empty.py")
    assert result.language == "python"
    assert result.symbols == []
    assert result.imports == []
    assert result.calls == []
    assert result.has_errors is False


def test_one_based_line_numbers(src_repo):
    """Line numbers in the response must be 1-based (not 0-based)."""
    result = CodeAnalyzerService.analyze_file(src_repo, "payment.py")
    cls = next(s for s in result.symbols if s.name == "PaymentService")
    # class PaymentService: is on line 3 in payment.py
    assert cls.start_line == 3


def test_qualified_name_method(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "payment.py")
    method = next(s for s in result.symbols if s.name == "process")
    assert method.qualified_name == "PaymentService.process"


def test_unsupported_file(src_repo):
    result = CodeAnalyzerService.analyze_file(src_repo, "style.css")
    assert result.language == "unsupported"
    assert result.symbols == []


def test_nonexistent_file_raises(src_repo):
    with pytest.raises(CodeParserError) as exc_info:
        CodeAnalyzerService.analyze_file(src_repo, "no_such_file.py")
    assert exc_info.value.code == "FILE_NOT_FOUND"


def test_path_traversal_raises(src_repo):
    with pytest.raises(CodeParserError) as exc_info:
        CodeAnalyzerService.analyze_file(src_repo, "../secret.txt")
    assert exc_info.value.code in ("PATH_TRAVERSAL_DETECTED", "FILE_NOT_FOUND")


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

def test_api_analyze_valid(src_repo):
    resp = client.post("/api/code/analyze", json={
        "repository_path": src_repo,
        "file_path": "payment.py",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "python"
    assert data["has_errors"] is False
    symbol_names = [s["name"] for s in data["symbols"]]
    assert "PaymentService" in symbol_names
    assert "process" in symbol_names
    assert "helper" in symbol_names


def test_api_analyze_missing_file(src_repo):
    resp = client.post("/api/code/analyze", json={
        "repository_path": src_repo,
        "file_path": "does_not_exist.py",
    })
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "FILE_NOT_FOUND"


def test_api_analyze_invalid_repository():
    resp = client.post("/api/code/analyze", json={
        "repository_path": "/totally/invalid/path/xyz",
        "file_path": "main.py",
    })
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_REPOSITORY"


def test_api_analyze_path_traversal(src_repo):
    resp = client.post("/api/code/analyze", json={
        "repository_path": src_repo,
        "file_path": "../../etc/passwd",
    })
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] in ("PATH_TRAVERSAL_DETECTED", "FILE_NOT_FOUND")


def test_api_analyze_response_schema(src_repo):
    """Verify every expected field is present in the response."""
    resp = client.post("/api/code/analyze", json={
        "repository_path": src_repo,
        "file_path": "payment.py",
    })
    assert resp.status_code == 200
    data = resp.json()
    for key in ("file_path", "language", "symbols", "imports", "calls",
                "has_errors", "error_count"):
        assert key in data, f"Missing field: {key}"
    if data["symbols"]:
        sym = data["symbols"][0]
        for key in ("name", "qualified_name", "symbol_type", "file_path",
                    "start_line", "end_line", "start_column", "end_column"):
            assert key in sym, f"Missing symbol field: {key}"
