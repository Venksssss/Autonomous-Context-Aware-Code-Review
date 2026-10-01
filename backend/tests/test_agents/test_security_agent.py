import pytest
import os
import tempfile
from app.agents.nodes.security_agent import security_agent_node
from app.agents.state import ReviewWorkflowState
from tests.test_llm.fake_provider import FakeLLMProvider
from app.schemas.agent_findings import Finding

@pytest.fixture
def temp_repo_with_file():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "app"), exist_ok=True)
        # 100 empty lines to satisfy bounds checking
        content = "\n" * 100
        with open(os.path.join(d, "app", "auth.py"), "w", encoding="utf-8") as f:
            f.write(content)
        yield d

def test_security_agent_node(temp_repo_with_file):
    provider = FakeLLMProvider()
    
    state = ReviewWorkflowState(
        repository_path=temp_repo_with_file,
        review_plan={"scope": ["security"]},
        review_request="Check for security issues",
        findings=[],
        errors=[]
    )
    
    result = security_agent_node(state, provider=provider)
    assert not result["errors"]
    
    findings = result["findings"]
    assert len(findings) == 1
    finding = findings[0]
    
    # Finding is a dict (model_dumped)
    assert finding["category"] == "security"
    assert finding["severity"] == "high"
    assert finding["file_path"] == "app/auth.py"
    assert finding["source_agent"] == "security"
    assert "SELECT * FROM" in finding["evidence"][0]

def test_security_agent_skips_if_not_in_scope(temp_repo_with_file):
    provider = FakeLLMProvider()
    
    state = ReviewWorkflowState(
        repository_path=temp_repo_with_file,
        review_plan={"scope": ["logic", "quality"]}, # security not in scope
        findings=[],
        errors=[]
    )
    
    result = security_agent_node(state, provider=provider)
    assert not result["findings"]
    assert not result["errors"]

def test_security_agent_validates_file_bounds(temp_repo_with_file):
    provider = FakeLLMProvider()
    
    state = ReviewWorkflowState(
        repository_path=temp_repo_with_file,
        review_plan={"scope": ["security"]},
        findings=[],
        errors=[]
    )
    
    # Since our temp_repo_with_file only has 100 lines, if the FakeLLMProvider returned start_line=47, it will pass.
    # What if file doesn't exist?
    
    state_bad_repo = dict(state)
    state_bad_repo["repository_path"] = "/does/not/exist/ever"
    
    result = security_agent_node(state_bad_repo, provider=provider)
    # The finding should be dropped because validate_finding fails on os.path.exists
    assert not result["findings"]
    assert not result["errors"]
