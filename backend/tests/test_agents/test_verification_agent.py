import pytest
from app.agents.nodes.verification_agent import verification_agent_node
from app.schemas.verification import VerificationResult
from tests.test_llm.fake_provider import FakeLLMProvider

class TestVerificationAgent:
    def test_no_findings(self):
        state = {"findings": []}
        result = verification_agent_node(state)
        assert result == {"verification_results": []}
        
    def test_no_runtime_result(self):
        state = {
            "findings": [{"id": "f1", "title": "Crash"}]
        }
        result = verification_agent_node(state, provider=FakeLLMProvider())
        assert len(result["verification_results"]) == 1
        assert result["verification_results"][0]["verification_status"] == "not_tested"
        
    def test_passed_runtime_result(self):
        state = {
            "findings": [{"id": "f1", "title": "Crash"}],
            "runtime_test_result": {
                "framework": "pytest", "status": "passed", "exit_code": 0,
                "duration_seconds": 1.0, "stdout": "", "stderr": ""
            }
        }
        result = verification_agent_node(state, provider=FakeLLMProvider())
        assert len(result["verification_results"]) == 1
        assert result["verification_results"][0]["verification_status"] == "inconclusive"
        assert result["verification_results"][0]["finding_id"] == "f1"
        
    def test_failed_runtime_with_evidence(self):
        stdout = """
=========================== short test summary info ============================
FAILED tests/test_main.py::test_crash - KeyError: 'foo'
"""
        state = {
            "findings": [{"id": "f1", "title": "Crash", "description": "KeyError"}],
            "runtime_test_result": {
                "framework": "pytest", "status": "failed", "exit_code": 1,
                "duration_seconds": 1.0, "stdout": stdout, "stderr": ""
            }
        }
        
        # Fake provider will return verified
        fake_provider = FakeLLMProvider()
        
        # Override the structured return
        import json
        def fake_invoke_structured(*args, **kwargs):
            return VerificationResult(
                finding_id="f1",
                verification_status="verified",
                explanation="The LLM verified it.",
                supporting_tests=[]
            )
            
        fake_provider.invoke_structured = fake_invoke_structured
        
        result = verification_agent_node(state, provider=fake_provider)
        assert len(result["verification_results"]) == 1
        res = result["verification_results"][0]
        assert res["verification_status"] == "verified"
        assert res["finding_id"] == "f1"
        assert "tests/test_main.py::test_crash" in res["supporting_tests"]
        
    def test_provider_failure(self):
        stdout = """
=========================== short test summary info ============================
FAILED tests/test_main.py::test_crash - KeyError: 'foo'
"""
        state = {
            "findings": [{"id": "f1", "title": "Crash", "description": "KeyError"}],
            "runtime_test_result": {
                "framework": "pytest", "status": "failed", "exit_code": 1,
                "duration_seconds": 1.0, "stdout": stdout, "stderr": ""
            }
        }
        
        fake_provider = FakeLLMProvider()
        def fake_invoke_structured(*args, **kwargs):
            raise Exception("LLM Error")
            
        fake_provider.invoke_structured = fake_invoke_structured
        
        result = verification_agent_node(state, provider=fake_provider)
        res = result["verification_results"][0]
        assert res["verification_status"] == "inconclusive"
        assert "LLM Error" in res["explanation"]
