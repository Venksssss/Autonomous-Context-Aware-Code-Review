import pytest
import os
import tempfile
import subprocess
from app.agents.nodes.context_agent import context_agent_node, _get_changed_lines
from app.agents.state import ReviewWorkflowState

@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init"], cwd=d, check=True)
        # Create a python file with some symbols
        auth_code = """
class AuthService:
    def authenticate(self, user_id):
        pass
"""
        with open(os.path.join(d, "auth.py"), "w", encoding="utf-8") as f:
            f.write(auth_code)
            
        payment_code = """
from auth import AuthService

class PaymentService:
    def process(self):
        auth = AuthService()
        auth.authenticate("123")
"""
        with open(os.path.join(d, "payment.py"), "w", encoding="utf-8") as f:
            f.write(payment_code)
            
        subprocess.run(["git", "add", "."], cwd=d, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=d, check=True)
        
        yield d

def test_get_changed_lines():
    patch = """@@ -1,3 +1,4 @@
 class AuthService:
     def authenticate(self, user_id):
-        pass
+        # do something
+        return True
"""
    lines = _get_changed_lines(patch)
    assert 3 in lines
    assert 4 in lines
    assert 5 not in lines

def test_context_agent_node_success(temp_repo):
    # Simulate a diff state
    patch_text = """@@ -1,3 +1,4 @@
 class AuthService:
     def authenticate(self, user_id):
-        pass
+        return True
"""
    state = ReviewWorkflowState(
        repository_path=temp_repo,
        diff={
            "files": [
                {
                    "path": "auth.py",
                    "change_type": "modified",
                    "patch": patch_text
                }
            ]
        },
        review_plan=None,
        context=None,
        findings=[],
        errors=[]
    )
    
    result = context_agent_node(state)
    assert not result["errors"]
    ctx = result["context"]
    assert ctx is not None
    assert "auth.py" in ctx["changed_files"]
    assert "AuthService.authenticate" in ctx["changed_symbols"]
    
    # Check symbols_context contains the cross-file reference
    sym_ctx = [c for c in ctx["symbols_context"] if c["symbol"] == "AuthService.authenticate"]
    assert len(sym_ctx) == 1
    assert any("PaymentService.process" in call.get("symbol", "") for call in sym_ctx[0]["called_by"])
    
    # Check related_files correctly extracts payment.py
    assert "related_files" in ctx
    assert "payment.py" in ctx["related_files"]
    assert "auth.py" not in ctx["related_files"]  # Excludes self

def test_context_agent_node_missing_inputs():
    state = ReviewWorkflowState() # Empty state
    result = context_agent_node(state)
    assert result["context"] is None
    assert not result["errors"] # Handled gracefully
