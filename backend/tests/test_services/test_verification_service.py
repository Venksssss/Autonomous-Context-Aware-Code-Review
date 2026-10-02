import pytest
from app.services.verification_service import VerificationService, TestFailure
from app.schemas.test_run import TestExecutionResult

class TestVerificationService:
    def test_parse_failures(self):
        stdout = """
=========================== short test summary info ============================
FAILED tests/test_auth.py::test_login - AssertionError: assert False
ERROR tests/test_db.py::test_connection - KeyError: 'db'
"""
        failures = VerificationService.parse_failures(stdout)
        assert len(failures) == 2
        assert failures[0].test_path == "tests/test_auth.py"
        assert failures[0].test_name == "test_login"
        assert failures[0].exception_type == "AssertionError"
        assert failures[1].test_path == "tests/test_db.py"
        assert failures[1].exception_type == "KeyError"

    def test_is_relevant_by_file(self):
        finding = {"file": "backend/app/auth.py", "title": "Auth issue", "description": "Fix auth"}
        failure = TestFailure(test_path="tests/test_auth.py", test_name="test_login", exception_type="AssertionError", message="assert False")
        assert VerificationService._is_relevant(finding, failure, {}) is True

    def test_is_relevant_by_test_name(self):
        finding = {"file": "main.py", "title": "Login issue", "description": "test_login is broken"}
        failure = TestFailure(test_path="tests/test_other.py", test_name="test_login", exception_type="AssertionError", message="assert False")
        assert VerificationService._is_relevant(finding, failure, {}) is True

    def test_is_relevant_by_exception_type(self):
        finding = {"file": "main.py", "title": "Crash", "description": "Raises KeyError"}
        failure = TestFailure(test_path="tests/test_main.py", test_name="test_run", exception_type="KeyError", message="KeyError: 'foo'")
        assert VerificationService._is_relevant(finding, failure, {}) is True
        
    def test_is_relevant_by_related_files(self):
        finding = {"file": "main.py", "title": "Crash", "description": "Crash"}
        failure = TestFailure(test_path="tests/test_auth.py", test_name="test_run", exception_type="AssertionError", message="assert False")
        context = {"related_files": ["tests/test_auth.py"]}
        assert VerificationService._is_relevant(finding, failure, context) is True

    def test_not_relevant(self):
        finding = {"file": "main.py", "title": "Crash", "description": "Crash"}
        failure = TestFailure(test_path="tests/test_other.py", test_name="test_run", exception_type="AssertionError", message="assert False")
        assert VerificationService._is_relevant(finding, failure, {}) is False

    def test_generate_candidate_passed(self):
        finding = {"id": "f1"}
        test_result = TestExecutionResult(
            framework="pytest", status="passed", exit_code=0, duration_seconds=1.0,
            stdout="", stderr="", tests_run=1, tests_passed=1
        )
        res = VerificationService.generate_candidate_result(finding, test_result)
        assert res.verification_status == "inconclusive"
        assert "All tests passed" in res.explanation

    def test_generate_candidate_no_test_result(self):
        finding = {"id": "f1"}
        res = VerificationService.generate_candidate_result(finding, None)
        assert res.verification_status == "not_tested"

    def test_generate_candidate_no_relevant_failures(self):
        finding = {"id": "f1", "file": "main.py", "title": "Crash"}
        stdout = """
=========================== short test summary info ============================
FAILED tests/test_other.py::test_other - AssertionError: assert False
"""
        test_result = TestExecutionResult(
            framework="pytest", status="failed", exit_code=1, duration_seconds=1.0,
            stdout=stdout, stderr="", tests_run=1, tests_failed=1
        )
        res = VerificationService.generate_candidate_result(finding, test_result)
        assert res.verification_status == "inconclusive"
        assert "no failures were deterministically matched" in res.explanation
        assert len(res.supporting_tests) == 0

    def test_generate_candidate_with_relevant_failures(self):
        finding = {"id": "f1", "file": "main.py", "title": "Crash", "description": "KeyError"}
        stdout = """
=========================== short test summary info ============================
FAILED tests/test_main.py::test_crash - KeyError: 'foo'
"""
        test_result = TestExecutionResult(
            framework="pytest", status="failed", exit_code=1, duration_seconds=1.0,
            stdout=stdout, stderr="", tests_run=1, tests_failed=1
        )
        res = VerificationService.generate_candidate_result(finding, test_result)
        assert res.verification_status == "inconclusive" # pending LLM semantic check
        assert len(res.supporting_tests) == 1
        assert res.supporting_tests[0] == "tests/test_main.py::test_crash"
