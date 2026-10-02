import pytest
import subprocess
import tempfile
import shutil
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.agents.graph import build_review_graph
from app.agents.state import ReviewWorkflowState
from app.agents.nodes.planner import planner_node, build_context_summary
from app.services.review_workflow import ReviewWorkflowService
from app.schemas.review_workflow import ReviewWorkflowResult
from tests.test_llm.fake_provider import FakeLLMProvider

client = TestClient(app)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def make_fake_service() -> ReviewWorkflowService:
    return ReviewWorkflowService(provider=FakeLLMProvider())


@pytest.fixture
def git_repo():
    """Create a minimal two-commit Git repository for integration tests."""
    tmp = tempfile.mkdtemp()
    repo = Path(tmp)
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp, check=True, capture_output=True)

    # Commit A
    (repo / "auth.py").write_text("def login(user): return True\n")
    subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp, check=True, capture_output=True)
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp, capture_output=True, text=True)
    commit_a = result.stdout.strip()

    # Commit B
    (repo / "auth.py").write_text("def login(user, password): return password == 'secret'\n")
    subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add password check"], cwd=tmp, check=True, capture_output=True)
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp, capture_output=True, text=True)
    commit_b = result.stdout.strip()

    yield {"path": tmp, "base": commit_a, "head": commit_b}
    shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# test_state.py
# ---------------------------------------------------------------------------

class TestState:
    def test_state_accepts_all_fields(self):
        state: ReviewWorkflowState = {
            "review_request": "check this",
            "repository_path": "/tmp/repo",
            "base_revision": "abc",
            "head_revision": "def",
            "diff": None,
            "review_plan": None,
            "context": None,
            "findings": [],
            "errors": [],
        }
        assert state["review_request"] == "check this"

    def test_state_has_no_infrastructure_objects(self):
        """State must contain only serializable data — no parser, client, or model objects."""
        state: ReviewWorkflowState = {
            "review_request": "x",
            "findings": [],
            "errors": [],
        }
        # All values must be JSON-friendly primitives
        import json
        json.dumps({k: v for k, v in state.items() if v is not None})

    def test_errors_reducer_appends(self):
        """
        LangGraph's 'add' reducer lets multiple nodes accumulate errors
        without clobbering each other.  Simulate by hand.
        """
        import operator
        a = ["err1"]
        b = ["err2"]
        combined = operator.add(a, b)
        assert combined == ["err1", "err2"]


# ---------------------------------------------------------------------------
# test_graph.py
# ---------------------------------------------------------------------------

class TestGraph:
    def test_graph_builds_successfully(self):
        graph = build_review_graph(provider=FakeLLMProvider())
        assert graph is not None

    def test_graph_executes(self):
        graph = build_review_graph(provider=FakeLLMProvider())
        result = graph.invoke({
            "review_request": "check auth",
            "findings": [],
            "errors": [],
        })
        assert result is not None

    def test_graph_produces_review_plan(self):
        graph = build_review_graph(provider=FakeLLMProvider())
        result = graph.invoke({
            "review_request": "check security",
            "findings": [],
            "errors": [],
        })
        assert result["review_plan"] is not None
        assert "scope" in result["review_plan"]
        assert "priority" in result["review_plan"]

    def test_graph_no_errors_on_valid_input(self):
        graph = build_review_graph(provider=FakeLLMProvider())
        result = graph.invoke({
            "review_request": "code quality review",
            "findings": [],
            "errors": [],
        })
        assert result["errors"] == []

    def test_graph_with_diff_context(self):
        graph = build_review_graph(provider=FakeLLMProvider())
        fake_diff = {
            "changed_files": [{"file_path": "auth.py", "patch": "+def login(): pass", "change_type": "modified"}],
            "total_additions": 1,
            "total_deletions": 0,
        }
        result = graph.invoke({
            "review_request": "auth changes",
            "diff": fake_diff,
            "findings": [],
            "errors": [],
        })
        assert result["review_plan"] is not None


# ---------------------------------------------------------------------------
# test_workflow.py
# ---------------------------------------------------------------------------

class TestWorkflow:
    def test_workflow_planner_only(self):
        svc = make_fake_service()
        result = svc.run(review_request="check code quality")
        assert isinstance(result, ReviewWorkflowResult)
        assert result.status == "planned"
        assert result.review_plan is not None
        assert result.errors == []

    def test_workflow_result_schema(self):
        svc = make_fake_service()
        result = svc.run(review_request="security review")
        assert result.review_plan.priority in ("low", "medium", "high")
        assert isinstance(result.review_plan.scope, list)
        assert isinstance(result.review_plan.required_context, list)

    def test_workflow_invalid_repo_returns_failed(self):
        svc = make_fake_service()
        result = svc.run(
            review_request="check",
            repository_path="/nonexistent/repo",
            base_revision="abc",
            head_revision="def",
        )
        assert result.status == "failed"
        assert len(result.errors) > 0

    def test_workflow_with_real_git_diff(self, git_repo):
        svc = make_fake_service()
        result = svc.run(
            review_request="Review the auth changes",
            repository_path=git_repo["path"],
            base_revision=git_repo["base"],
            head_revision=git_repo["head"],
        )
        assert result.status == "completed"
        assert result.review_plan is not None
        assert result.errors == []

    def test_planner_node_directly(self):
        state: ReviewWorkflowState = {
            "review_request": "check auth",
            "findings": [],
            "errors": [],
        }
        update = planner_node(state, provider=FakeLLMProvider())
        assert update["review_plan"] is not None
        assert update["errors"] == []

    def test_planner_node_failure_captured(self):
        from tests.test_llm.fake_provider import FakeLLMProvider as Fake

        class FailingProvider(Fake):
            def structured_invoke(self, messages, schema):
                raise RuntimeError("LLM down")

        state: ReviewWorkflowState = {
            "review_request": "test",
            "findings": [],
            "errors": [],
        }
        update = planner_node(state, provider=FailingProvider())
        assert update["review_plan"] is None
        assert len(update["errors"]) > 0

    def test_build_context_summary_with_diff(self):
        state: ReviewWorkflowState = {
            "review_request": "x",
            "diff": {
                "changed_files": [{"file_path": "auth.py", "patch": "+login()", "change_type": "modified"}],
                "total_additions": 1,
                "total_deletions": 0,
            },
            "findings": [],
            "errors": [],
        }
        summary = build_context_summary(state)
        assert summary is not None
        assert "auth.py" in summary["changed_files"]

    def test_build_context_summary_no_diff(self):
        state: ReviewWorkflowState = {"review_request": "x", "findings": [], "errors": []}
        summary = build_context_summary(state)
        assert summary is None


# ---------------------------------------------------------------------------
# API integration
# ---------------------------------------------------------------------------

class TestReviewAPI:
    def test_api_review_plan_only_with_fake(self, monkeypatch):
        from app.services.review_workflow import ReviewWorkflowService as RWS
        orig_init = RWS.__init__

        def fake_init(self, provider=None):
            orig_init(self, provider=FakeLLMProvider())

        monkeypatch.setattr(RWS, "__init__", fake_init)

        resp = client.post("/api/ai/review", json={
            "review_request": "Review for security issues."
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "planned"
        assert data["review_plan"]["priority"] == "high"

    def test_api_review_with_bad_repo(self, monkeypatch):
        from app.services.review_workflow import ReviewWorkflowService as RWS
        orig_init = RWS.__init__

        def fake_init(self, provider=None):
            orig_init(self, provider=FakeLLMProvider())

        monkeypatch.setattr(RWS, "__init__", fake_init)

        resp = client.post("/api/ai/review", json={
            "review_request": "check",
            "repository_path": "/invalid/path",
            "base_revision": "abc",
            "head_revision": "def",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert len(data["errors"]) > 0

    def test_api_review_with_real_git_diff(self, git_repo, monkeypatch):
        from app.services.review_workflow import ReviewWorkflowService as RWS
        orig_init = RWS.__init__

        def fake_init(self, provider=None):
            orig_init(self, provider=FakeLLMProvider())

        monkeypatch.setattr(RWS, "__init__", fake_init)

        resp = client.post("/api/ai/review", json={
            "review_request": "Review the auth changes for security",
            "repository_path": git_repo["path"],
            "base_revision": git_repo["base"],
            "head_revision": git_repo["head"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["review_plan"] is not None
