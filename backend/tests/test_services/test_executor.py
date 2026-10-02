import os
import shutil
import tempfile
import pytest
from pathlib import Path

from app.schemas.test_run import TestExecutionRequest
from app.services.test_executor import TestExecutorService, TestExecutionError, PytestSummaryParser

@pytest.fixture
def temp_repo():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)

class TestPytestSummaryParser:
    def test_parse_all_passed(self):
        output = "======= 14 passed in 2.10s ======="
        res = PytestSummaryParser.parse_summary(output)
        assert res["tests_passed"] == 14
        assert res["tests_run"] == 14
        assert res["tests_failed"] == 0
        
    def test_parse_mixed_results(self):
        output = "======= 12 passed, 2 failed in 3.21s ======="
        res = PytestSummaryParser.parse_summary(output)
        assert res["tests_passed"] == 12
        assert res["tests_failed"] == 2
        assert res["tests_run"] == 14
        
    def test_parse_with_skipped(self):
        output = "======= 10 passed, 1 skipped in 2.00s ======="
        res = PytestSummaryParser.parse_summary(output)
        assert res["tests_passed"] == 10
        assert res["tests_skipped"] == 1
        assert res["tests_failed"] == 0
        assert res["tests_run"] == 11
        
    def test_parse_with_errors(self):
        output = "======= 1 failed, 3 error in 4.00s ======="
        res = PytestSummaryParser.parse_summary(output)
        assert res["tests_passed"] == 0
        assert res["tests_failed"] == 1
        assert res["tests_errors"] == 3
        assert res["tests_run"] == 4
        
    def test_parse_malformed_output(self):
        output = "some random crash output without summary"
        res = PytestSummaryParser.parse_summary(output)
        assert res["tests_passed"] is None
        assert res["tests_run"] is None

class TestTestExecutorService:
    def test_execute_passing_test(self, temp_repo):
        # Create a passing test
        test_path = os.path.join(temp_repo, "test_pass.py")
        with open(test_path, "w") as f:
            f.write("def test_ok():\n    assert True\n")
            
        service = TestExecutorService()
        req = TestExecutionRequest(repository_path=temp_repo)
        res = service.execute_tests(req)
        
        assert res.status == "passed"
        assert res.exit_code == 0
        assert res.tests_run == 1
        assert res.tests_passed == 1
        assert res.tests_failed == 0
        assert "test_pass.py" in res.stdout
        
    def test_execute_failing_test(self, temp_repo):
        test_path = os.path.join(temp_repo, "test_fail.py")
        with open(test_path, "w") as f:
            f.write("def test_bad():\n    assert False\n")
            
        service = TestExecutorService()
        req = TestExecutionRequest(repository_path=temp_repo)
        res = service.execute_tests(req)
        
        assert res.status == "failed"
        assert res.exit_code == 1
        assert res.tests_run == 1
        assert res.tests_passed == 0
        assert res.tests_failed == 1
        
    def test_invalid_repository(self):
        service = TestExecutorService()
        req = TestExecutionRequest(repository_path="/nonexistent/path/12345")
        with pytest.raises(TestExecutionError, match="TEST_TARGET_INVALID"):
            service.execute_tests(req)
            
    def test_path_traversal(self, temp_repo):
        service = TestExecutorService()
        # Attempt to target a path outside the repository
        req = TestExecutionRequest(repository_path=temp_repo, test_path="../other_dir")
        with pytest.raises(TestExecutionError, match="TEST_TARGET_OUTSIDE_REPOSITORY"):
            service.execute_tests(req)
            
    def test_timeout(self, temp_repo):
        test_path = os.path.join(temp_repo, "test_sleep.py")
        with open(test_path, "w") as f:
            f.write("import time\ndef test_sleep():\n    time.sleep(2)\n    assert True\n")
            
        # Set a very short timeout
        service = TestExecutorService(timeout_seconds=0.5)
        req = TestExecutionRequest(repository_path=temp_repo)
        res = service.execute_tests(req)
        
        assert res.status == "timeout"
        assert "timeout" in res.stdout.lower()
        
    def test_output_truncation(self, temp_repo):
        test_path = os.path.join(temp_repo, "test_spam.py")
        with open(test_path, "w") as f:
            f.write("def test_spam():\n    print('x' * 1000)\n    assert True\n")
            
        service = TestExecutorService(max_output_chars=100)
        req = TestExecutionRequest(repository_path=temp_repo)
        res = service.execute_tests(req)
        
        assert res.output_truncated is True
        assert "[STDOUT TRUNCATED]" in res.stdout
