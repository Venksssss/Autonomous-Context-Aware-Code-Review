import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.schemas.verification import VerificationResult, VerificationStatus
from app.schemas.test_run import TestExecutionResult

class TestFailure(BaseModel):
    __test__ = False
    test_path: str
    test_name: str
    exception_type: str
    message: str

class VerificationService:
    """
    Deterministically extracts test failure evidence from a TestExecutionResult,
    and identifies which failures might be relevant to specific findings.
    """

    @staticmethod
    def parse_failures(stdout: str) -> List[TestFailure]:
        failures = []
        in_short_summary = False
        
        # We need to handle potential truncation markers in stdout safely
        lines = stdout.split('\n')
        for line in lines:
            line = line.strip()
            
            if "short test summary info" in line.lower():
                in_short_summary = True
                continue
                
            if in_short_summary and line.startswith("="):
                break
                
            if in_short_summary and (line.startswith("FAILED ") or line.startswith("ERROR ")):
                # FAILED tests/test_auth.py::test_login - AssertionError: assert False
                parts = line.split(" - ", 1)
                left = parts[0].replace("FAILED ", "").replace("ERROR ", "").strip()
                message = parts[1].strip() if len(parts) > 1 else ""
                
                left_parts = left.split("::")
                test_path = left_parts[0]
                test_name = left_parts[1] if len(left_parts) > 1 else ""
                
                exception_type = ""
                if ":" in message:
                    exception_type = message.split(":")[0].strip()
                
                failures.append(TestFailure(
                    test_path=test_path,
                    test_name=test_name,
                    exception_type=exception_type,
                    message=message
                ))
                
        return failures

    @staticmethod
    def _is_relevant(finding: Dict[str, Any], failure: TestFailure, context: Dict[str, Any]) -> bool:
        finding_file = finding.get("file", "") or ""
        finding_desc = finding.get("description", "") or ""
        finding_title = finding.get("title", "") or ""
        
        finding_text = f"{finding_title} {finding_desc}".lower()
        
        # 1. Match by file base name
        if finding_file:
            finding_file_base = finding_file.split("/")[-1].replace(".py", "")
            test_file_base = failure.test_path.split("/")[-1].replace("test_", "").replace(".py", "")
            
            if finding_file_base and test_file_base and (finding_file_base in test_file_base or test_file_base in finding_file_base):
                return True
                
        # 2. Match by test name mentioned in finding text
        if failure.test_name and failure.test_name.lower() in finding_text:
            return True
            
        # 3. Match by exception type mentioned in finding text
        if failure.exception_type and failure.exception_type.lower() in finding_text:
            return True
            
        # 4. Check repository context related files (if any context provided)
        # Assuming context might have a mapping of file -> related files
        related_files = context.get("related_files", [])
        if isinstance(related_files, list):
            for rf in related_files:
                if isinstance(rf, str) and rf in failure.test_path:
                    return True
                    
        return False

    @staticmethod
    def identify_evidence(
        finding: Dict[str, Any], 
        test_result: Optional[TestExecutionResult], 
        context: Optional[Dict[str, Any]] = None
    ) -> List[TestFailure]:
        
        if not test_result or not test_result.stdout:
            return []
            
        context = context or {}
        all_failures = VerificationService.parse_failures(test_result.stdout)
        
        relevant_failures = []
        for failure in all_failures:
            if VerificationService._is_relevant(finding, failure, context):
                relevant_failures.append(failure)
                
        return relevant_failures
        
    @staticmethod
    def generate_candidate_result(
        finding: Dict[str, Any], 
        test_result: Optional[TestExecutionResult], 
        context: Optional[Dict[str, Any]] = None
    ) -> VerificationResult:
        """
        Creates a baseline VerificationResult deterministically.
        If there are failures and we matched some, we output them for the LLM to analyze,
        or we default to inconclusive/not_tested.
        """
        finding_id = finding.get("id", "unknown")
        
        if not test_result or test_result.status == "unknown":
            return VerificationResult(
                finding_id=finding_id,
                verification_status="not_tested",
                runtime_evidence=test_result,
                supporting_tests=[],
                explanation="No valid runtime test results were available."
            )
            
        if test_result.status == "passed":
            return VerificationResult(
                finding_id=finding_id,
                verification_status="inconclusive",
                runtime_evidence=test_result,
                supporting_tests=[],
                explanation="All tests passed. Passing tests do not conclusively prove the absence of this issue (e.g., performance or security vulnerabilities)."
            )
            
        # Tests failed, let's look for evidence
        relevant_failures = VerificationService.identify_evidence(finding, test_result, context)
        
        if not relevant_failures:
            return VerificationResult(
                finding_id=finding_id,
                verification_status="inconclusive",
                runtime_evidence=test_result,
                supporting_tests=[],
                explanation="Tests failed, but no failures were deterministically matched to this finding."
            )
            
        supporting = [f"{f.test_path}::{f.test_name}" for f in relevant_failures]
        
        return VerificationResult(
            finding_id=finding_id,
            verification_status="inconclusive", # The LLM can upgrade this to verified/contradicted
            runtime_evidence=test_result,
            supporting_tests=supporting,
            explanation="Relevant test failures were found and need semantic interpretation."
        )
