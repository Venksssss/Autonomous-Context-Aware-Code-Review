import os
import sys
import time
import subprocess
import re
from pathlib import Path
from typing import Optional, Tuple
from app.schemas.test_run import TestExecutionRequest, TestExecutionResult, TestStatus

class TestExecutionError(Exception):
    pass

class TestTimeoutError(Exception):
    pass

class PytestSummaryParser:
    @staticmethod
    def parse_summary(stdout: str) -> dict:
        """
        Parses pytest output to extract test run statistics.
        Examples:
        "14 passed in 2.10s"
        "12 passed, 2 failed in 3.21s"
        "10 passed, 1 skipped in 2.00s"
        "1 failed, 3 errors in 4.00s"
        """
        results = {
            "tests_run": None,
            "tests_passed": None,
            "tests_failed": None,
            "tests_skipped": None,
            "tests_errors": None,
        }
        
        # Look for the summary line, usually starts with '=' and ends with 's' or similar,
        # but let's just look for lines containing "passed", "failed", "skipped", "error" near the end.
        
        # Pytest summary line example: "======= 1 failed, 13 passed, 1 skipped in 0.12s ======="
        # Or: "======= 14 passed in 2.10s ======="
        
        # We will match the last line that matches the typical summary pattern.
        lines = stdout.strip().split('\n')
        summary_line = ""
        for line in reversed(lines):
            line = line.strip("= ")
            if re.search(r'\bin \d+\.\d+s\b', line) and (
                'passed' in line or 'failed' in line or 'skipped' in line or 'error' in line
            ):
                summary_line = line
                break
                
        if not summary_line:
            # Maybe the test collection failed, or output is totally unparsable.
            return results
            
        passed = 0
        failed = 0
        skipped = 0
        errors = 0
        
        # Extract counts
        passed_match = re.search(r'(\d+)\s+passed', summary_line)
        if passed_match:
            passed = int(passed_match.group(1))
            
        failed_match = re.search(r'(\d+)\s+failed', summary_line)
        if failed_match:
            failed = int(failed_match.group(1))
            
        skipped_match = re.search(r'(\d+)\s+skipped', summary_line)
        if skipped_match:
            skipped = int(skipped_match.group(1))
            
        error_match = re.search(r'(\d+)\s+error', summary_line)
        if error_match:
            errors = int(error_match.group(1))
            
        results["tests_passed"] = passed
        results["tests_failed"] = failed
        results["tests_skipped"] = skipped
        results["tests_errors"] = errors
        results["tests_run"] = passed + failed + skipped + errors
        
        return results

class TestExecutorService:
    def __init__(self, timeout_seconds: float = 60.0, max_output_chars: int = 50000):
        self.timeout_seconds = timeout_seconds
        self.max_output_chars = max_output_chars

    def execute_tests(self, request: TestExecutionRequest) -> TestExecutionResult:
        repo_path = Path(request.repository_path).resolve()
        
        if not repo_path.exists() or not repo_path.is_dir():
            raise TestExecutionError("TEST_TARGET_INVALID")
            
        # Path validation
        if request.test_path:
            target_path = (repo_path / request.test_path).resolve()
            if not str(target_path).startswith(str(repo_path)):
                raise TestExecutionError("TEST_TARGET_OUTSIDE_REPOSITORY")
            if not target_path.exists():
                raise TestExecutionError("TEST_TARGET_INVALID")
            target = str(target_path)
        else:
            target = str(repo_path)
            
        cmd = [sys.executable, "-m", "pytest"]
        if request.test_path:
            cmd.append(target)
            
        start_time = time.time()
        
        stdout_data = ""
        stderr_data = ""
        exit_code = None
        status: TestStatus = "unknown"
        
        try:
            # We run pytest using subprocess.run
            # Avoid shell=True to prevent injection
            process = subprocess.run(
                cmd,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds
            )
            
            stdout_data = process.stdout
            stderr_data = process.stderr
            exit_code = process.returncode
            
            # Determine status
            # pytest exit codes:
            # 0: all tests passed
            # 1: tests were collected and run but some failed
            # 2: test execution was interrupted
            # 3: internal error happened
            # 4: pytest usage error
            # 5: no tests collected
            if exit_code == 0:
                status = "passed"
            elif exit_code == 1:
                status = "failed"
            elif exit_code == 5:
                status = "passed" # No tests collected, technically didn't fail
            else:
                status = "error"
                
        except subprocess.TimeoutExpired as e:
            status = "timeout"
            if e.stdout:
                if isinstance(e.stdout, bytes):
                    stdout_data = e.stdout.decode(errors='replace')
                else:
                    stdout_data = e.stdout
            if e.stderr:
                if isinstance(e.stderr, bytes):
                    stderr_data = e.stderr.decode(errors='replace')
                else:
                    stderr_data = e.stderr
            
            stdout_data += f"\n\n[Process terminated after {self.timeout_seconds}s timeout]"
            
        except Exception as e:
            status = "error"
            stderr_data = str(e)
            
        duration = time.time() - start_time
        
        # Truncate output if necessary
        output_truncated = False
        if len(stdout_data) > self.max_output_chars:
            stdout_data = stdout_data[:self.max_output_chars] + "\n\n...[STDOUT TRUNCATED]..."
            output_truncated = True
            
        if len(stderr_data) > self.max_output_chars:
            stderr_data = stderr_data[:self.max_output_chars] + "\n\n...[STDERR TRUNCATED]..."
            output_truncated = True
            
        # Parse pytest summary
        summary = PytestSummaryParser.parse_summary(stdout_data)
        
        # If exit_code == 0 but parser says tests failed, trust parser (though rare)
        if summary["tests_failed"] and summary["tests_failed"] > 0 and status == "passed":
            status = "failed"
            
        return TestExecutionResult(
            framework="pytest",
            status=status,
            exit_code=exit_code,
            duration_seconds=duration,
            stdout=stdout_data,
            stderr=stderr_data,
            tests_run=summary["tests_run"],
            tests_passed=summary["tests_passed"],
            tests_failed=summary["tests_failed"],
            tests_skipped=summary["tests_skipped"],
            tests_errors=summary["tests_errors"],
            output_truncated=output_truncated
        )
