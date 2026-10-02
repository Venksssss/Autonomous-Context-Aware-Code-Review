from typing import List, Literal, Optional
from pydantic import BaseModel

TestFramework = Literal["pytest"]
TestStatus = Literal["passed", "failed", "error", "timeout", "unknown"]
TestKind = Literal["test_file", "test_dir"]

class DiscoveredTest(BaseModel):
    path: str
    framework: TestFramework
    kind: TestKind

class TestDiscoveryResult(BaseModel):
    framework: Optional[TestFramework] = None
    tests: List[DiscoveredTest] = []
    test_count: int = 0

class TestExecutionRequest(BaseModel):
    __test__ = False
    repository_path: str
    test_path: Optional[str] = None
    execution_mode: Literal["local", "docker"] = "local"

class TestExecutionResult(BaseModel):
    __test__ = False
    framework: TestFramework
    execution_mode: Literal["local", "docker"] = "local"
    sandboxed: bool = False
    status: TestStatus
    exit_code: Optional[int]
    duration_seconds: float
    stdout: str
    stderr: str
    tests_run: Optional[int] = None
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None
    tests_skipped: Optional[int] = None
    tests_errors: Optional[int] = None
    output_truncated: bool = False
