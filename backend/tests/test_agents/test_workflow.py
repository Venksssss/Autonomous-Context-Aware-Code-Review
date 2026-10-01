import pytest
import os
import tempfile
import subprocess
from app.agents.graph import build_review_graph
from app.agents.state import ReviewWorkflowState
from tests.test_llm.fake_provider import FakeLLMProvider

@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init"], cwd=d, check=True)
        os.makedirs(os.path.join(d, "app"), exist_ok=True)
        # Create file with 100 lines
        auth_code = "\n" * 45 + """
class AuthService:
    def authenticate(self, user_id):
        user = db.get(user_id)
        SELECT * FROM users WHERE id = user_id
        return True
""" + "\n" * 45
        with open(os.path.join(d, "app", "auth.py"), "w", encoding="utf-8") as f:
            f.write(auth_code)
            
        subprocess.run(["git", "add", "."], cwd=d, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=d, check=True)
        
        yield d

def test_full_workflow_parallel_findings(temp_repo):
    provider = FakeLLMProvider()
    graph = build_review_graph(provider=provider)
    
    # We simulate starting the graph with basic inputs
    # Normally the ReviewWorkflowService provides this state, but we can test the graph directly.
    # To get findings from FakeLLMProvider, we need to pass a prompt that triggers both.
    # We will trigger the test mode by providing a generic request that mentions both.
    request = "Check for security code reviewer and quality and logic code reviewer issues."
    
    initial_state = {
        "review_request": request,
        "repository_path": temp_repo,
        # Fake a diff so context agent has something
        "diff": {
            "files": [
                {
                    "path": "app/auth.py",
                    "change_type": "modified",
                    "patch": "@@ -46,3 +46,4 @@\n class AuthService:\n     def authenticate(self, user_id):\n+        return True\n"
                }
            ]
        },
        "errors": [],
        "findings": []
    }
    
    result = graph.invoke(initial_state)
    
    # Check that both security and quality findings are present
    assert not result.get("errors")
    
    findings = result.get("findings", [])
    # 1 from security, 1 from quality
    assert len(findings) == 2
    
    agents = [f["source_agent"] for f in findings]
    assert "security" in agents
    assert "quality" in agents
    
    # Check context was generated
    assert result.get("context") is not None
    assert "app/auth.py" in result["context"]["changed_files"]
