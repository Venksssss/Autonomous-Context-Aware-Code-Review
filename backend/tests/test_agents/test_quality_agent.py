import pytest
import os
import tempfile
from app.agents.nodes.quality_agent import quality_agent_node
from app.agents.state import ReviewWorkflowState
from tests.test_llm.fake_provider import FakeLLMProvider

@pytest.fixture
def temp_repo_with_file():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "app"), exist_ok=True)
        content = "\n" * 100
        with open(os.path.join(d, "app", "auth.py"), "w", encoding="utf-8") as f:
            f.write(content)
        yield d

def test_quality_agent_node(temp_repo_with_file):
    provider = FakeLLMProvider()
    
    state = ReviewWorkflowState(
        repository_path=temp_repo_with_file,
        review_plan={"scope": ["quality"]},
        review_request="Check for quality and logic code reviewer issues",
        findings=[],
        errors=[]
    )
    
    result = quality_agent_node(state, provider=provider)
    assert not result["errors"]
    
    findings = result["findings"]
    assert len(findings) == 1
    finding = findings[0]
    
    assert finding["category"] == "logic"
    assert finding["severity"] == "medium"
    assert finding["file_path"] == "app/auth.py"
    assert finding["source_agent"] == "quality"
    assert "user = db.get" in finding["evidence"][0]

def test_quality_agent_skips_if_not_in_scope(temp_repo_with_file):
    provider = FakeLLMProvider()
    
    state = ReviewWorkflowState(
        repository_path=temp_repo_with_file,
        review_plan={"scope": ["security"]}, # quality/logic not in scope
        findings=[],
        errors=[]
    )
    
    result = quality_agent_node(state, provider=provider)
    assert not result["findings"]
    assert not result["errors"]
