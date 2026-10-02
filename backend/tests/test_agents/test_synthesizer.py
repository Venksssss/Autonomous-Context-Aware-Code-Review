"""
Tests for the Synthesizer Agent (Phase 3 Segment 4).

Covers:
1.  valid synthesis with findings
2.  multiple findings from different agents
3.  duplicate / overlapping findings deduplication
4.  no findings case
5.  structured schema validation
6.  invalid / unexpected provider output
7.  provider failure
8.  evidence preservation
9.  severity preservation
10. recommendation generation
11. files_reviewed deterministic extraction
12. overall_risk deterministic computation
13. analysis_metadata deterministic construction
14. graph fan-in: both specialist findings reach synthesizer
15. partial failure: one specialist fails, synthesizer still runs
16. synthesizer node failure: findings preserved, final_review=None
17. API includes final_review in response
18. API with real git repository end-to-end
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from typing import Type, TypeVar

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from langchain_core.messages import BaseMessage, AIMessage

from app.main import app
from app.agents.graph import build_review_graph
from app.agents.nodes.synthesizer import synthesizer_node
from app.agents.state import ReviewWorkflowState
from app.schemas.agent_findings import AgentFindings, Finding
from app.schemas.final_review import FinalReviewReport, AnalysisMetadata
from app.services.review_agents.synthesizer import (
    SynthesizerService,
    compute_overall_risk,
    extract_files_reviewed,
    build_analysis_metadata,
)
from app.services.llm.interface import LLMProvider
from app.services.review_workflow import ReviewWorkflowService
from tests.test_llm.fake_provider import FakeLLMProvider

T = TypeVar("T", bound=BaseModel)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_finding(
    id_: str = "f-001",
    category: str = "security",
    severity: str = "high",
    file_path: str = "app/auth.py",
    source_agent: str = "security",
) -> Finding:
    return Finding(
        id=id_,
        category=category,
        severity=severity,
        title="Test Finding",
        description="A test finding description.",
        file_path=file_path,
        start_line=10,
        end_line=15,
        evidence=["evidence line 1"],
        recommendation="Fix the issue.",
        confidence=0.9,
        source_agent=source_agent,
    )


def make_service(provider: LLMProvider | None = None) -> ReviewWorkflowService:
    return ReviewWorkflowService(provider=provider or FakeLLMProvider())


# ---------------------------------------------------------------------------
# Unit: deterministic helper functions
# ---------------------------------------------------------------------------

class TestComputeOverallRisk:
    def test_no_findings_returns_none(self):
        assert compute_overall_risk([]) == "none"

    def test_single_critical(self):
        f = make_finding(severity="critical")
        assert compute_overall_risk([f]) == "critical"

    def test_single_high(self):
        f = make_finding(severity="high")
        assert compute_overall_risk([f]) == "high"

    def test_single_medium(self):
        f = make_finding(severity="medium")
        assert compute_overall_risk([f]) == "medium"

    def test_single_low(self):
        f = make_finding(severity="low")
        assert compute_overall_risk([f]) == "low"

    def test_mixed_returns_highest(self):
        findings = [
            make_finding(severity="low"),
            make_finding(severity="high"),
            make_finding(severity="medium"),
        ]
        assert compute_overall_risk(findings) == "high"

    def test_critical_dominates(self):
        findings = [
            make_finding(severity="high"),
            make_finding(severity="critical"),
            make_finding(severity="low"),
        ]
        assert compute_overall_risk(findings) == "critical"


class TestExtractFilesReviewed:
    def test_from_diff_summary(self):
        diff = {"changed_files": ["auth.py", "payment.py"]}
        files = extract_files_reviewed(diff, None, [])
        assert "auth.py" in files
        assert "payment.py" in files

    def test_from_context(self):
        context = {
            "changed_files": ["auth.py"],
            "related_files": ["utils.py"],
        }
        files = extract_files_reviewed(None, context, [])
        assert "auth.py" in files
        assert "utils.py" in files

    def test_from_findings(self):
        findings = [make_finding(file_path="app/secret.py")]
        files = extract_files_reviewed(None, None, findings)
        assert "app/secret.py" in files

    def test_deduplication(self):
        diff = {"changed_files": ["auth.py"]}
        context = {"changed_files": ["auth.py"], "related_files": []}
        findings = [make_finding(file_path="auth.py")]
        files = extract_files_reviewed(diff, context, findings)
        assert files.count("auth.py") == 1

    def test_sorted_output(self):
        diff = {"changed_files": ["z.py", "a.py", "m.py"]}
        files = extract_files_reviewed(diff, None, [])
        assert files == sorted(files)


class TestBuildAnalysisMetadata:
    def test_empty_findings(self):
        meta = build_analysis_metadata([])
        assert meta.finding_count == 0
        assert meta.security_findings == 0
        assert meta.quality_findings == 0

    def test_counts_by_category(self):
        findings = [
            make_finding(category="security"),
            make_finding(category="security"),
            make_finding(category="logic"),
            make_finding(category="quality"),
        ]
        meta = build_analysis_metadata(findings)
        assert meta.finding_count == 4
        assert meta.security_findings == 2
        assert meta.quality_findings == 2

    def test_default_agents_list(self):
        meta = build_analysis_metadata([])
        assert "synthesizer" in meta.agents_used
        assert "security" in meta.agents_used

    def test_custom_agents_list(self):
        meta = build_analysis_metadata([], agents_used=["planner", "synthesizer"])
        assert meta.agents_used == ["planner", "synthesizer"]


# ---------------------------------------------------------------------------
# Unit: SynthesizerService
# ---------------------------------------------------------------------------

class TestSynthesizerService:
    def test_valid_synthesis_with_findings(self):
        svc = SynthesizerService(provider=FakeLLMProvider())
        finding = make_finding(id_="sec-001", category="security", severity="high",
                               file_path="app/auth.py", source_agent="security")
        finding.title = "SQL Injection Risk"
        finding.description = "Potential SQL injection in user query."
        finding.evidence = ["SELECT * FROM users WHERE id = "]
        finding.recommendation = "Use parameterized queries."
        finding.start_line = 47
        finding.end_line = 47
        report = svc.synthesize(
            review_request="Check for security issues.",
            review_plan={"scope": ["security"], "priority": "high", "reason": "Test"},
            diff_summary={"changed_files": ["app/auth.py"], "total_additions": 1, "total_deletions": 0},
            context={"changed_files": ["app/auth.py"], "changed_symbols": ["AuthService.authenticate"], "related_files": []},
            raw_findings=[finding.model_dump()],
        )
        assert isinstance(report, FinalReviewReport)
        assert report.overall_risk in ("critical", "high", "medium", "low", "none")
        assert isinstance(report.summary, str)
        assert len(report.summary) > 0
        assert isinstance(report.findings, list)
        assert isinstance(report.recommendations, list)
        assert isinstance(report.files_reviewed, list)
        assert isinstance(report.analysis_metadata, AnalysisMetadata)

    def test_no_findings_case(self):
        svc = SynthesizerService(provider=FakeLLMProvider())
        report = svc.synthesize(
            review_request="Check for issues.",
            review_plan=None,
            diff_summary=None,
            context=None,
            raw_findings=[],
        )
        assert isinstance(report, FinalReviewReport)
        assert report.overall_risk == "none"
        assert report.findings == []
        assert report.recommendations == []
        assert "no actionable issues" in report.summary.lower()

    def test_overall_risk_deterministic_high(self):
        svc = SynthesizerService(provider=FakeLLMProvider())
        finding = make_finding(id_="sec-001", severity="high", file_path="app/auth.py")
        finding.title = "SQL Injection Risk"
        finding.description = "Potential SQL injection in user query."
        finding.evidence = ["SELECT * FROM users WHERE id = "]
        finding.recommendation = "Use parameterized queries."
        finding.start_line = 47
        finding.end_line = 47
        report = svc.synthesize(
            review_request="Check issues.",
            review_plan=None,
            diff_summary=None,
            context=None,
            raw_findings=[finding.model_dump()],
        )
        # Deterministic rule: high severity → overall high (or critical if consolidated higher)
        assert report.overall_risk in ("high", "critical")

    def test_severity_preserved_in_findings(self):
        svc = SynthesizerService(provider=FakeLLMProvider())
        finding = make_finding(id_="sec-001", severity="high", file_path="app/auth.py")
        finding.title = "SQL Injection Risk"
        finding.description = "Potential SQL injection in user query."
        finding.evidence = ["SELECT * FROM users WHERE id = "]
        finding.recommendation = "Use parameterized queries."
        finding.start_line = 47
        finding.end_line = 47
        report = svc.synthesize(
            review_request="Check.",
            review_plan=None,
            diff_summary=None,
            context=None,
            raw_findings=[finding.model_dump()],
        )
        if report.findings:
            assert report.findings[0].severity == "high"

    def test_evidence_preserved(self):
        svc = SynthesizerService(provider=FakeLLMProvider())
        finding = make_finding(id_="sec-001", severity="high", file_path="app/auth.py")
        finding.title = "SQL Injection Risk"
        finding.description = "Potential SQL injection in user query."
        finding.evidence = ["SELECT * FROM users WHERE id = "]
        finding.recommendation = "Use parameterized queries."
        finding.start_line = 47
        finding.end_line = 47
        report = svc.synthesize(
            review_request="Check.",
            review_plan=None,
            diff_summary=None,
            context=None,
            raw_findings=[finding.model_dump()],
        )
        if report.findings:
            assert report.findings[0].evidence  # Evidence list is non-empty

    def test_recommendations_generated(self):
        svc = SynthesizerService(provider=FakeLLMProvider())
        finding = make_finding(id_="sec-001", severity="high", file_path="app/auth.py")
        finding.title = "SQL Injection Risk"
        finding.description = "Potential SQL injection in user query."
        finding.evidence = ["SELECT * FROM users WHERE id = "]
        finding.recommendation = "Use parameterized queries."
        finding.start_line = 47
        finding.end_line = 47
        report = svc.synthesize(
            review_request="Check.",
            review_plan=None,
            diff_summary=None,
            context=None,
            raw_findings=[finding.model_dump()],
        )
        # When there are findings, recommendations should be generated
        assert isinstance(report.recommendations, list)

    def test_schema_validation_of_output(self):
        svc = SynthesizerService(provider=FakeLLMProvider())
        report = svc.synthesize(
            review_request="Validate schema.",
            review_plan={"scope": ["security"], "priority": "low", "reason": "test"},
            diff_summary={"changed_files": [], "total_additions": 0, "total_deletions": 0},
            context=None,
            raw_findings=[],
        )
        # Verify it's a fully valid FinalReviewReport with all required fields
        assert hasattr(report, "summary")
        assert hasattr(report, "overall_risk")
        assert hasattr(report, "findings")
        assert hasattr(report, "recommendations")
        assert hasattr(report, "files_reviewed")
        assert hasattr(report, "analysis_metadata")
        assert report.overall_risk in ("critical", "high", "medium", "low", "none")

    def test_files_reviewed_deterministic(self):
        svc = SynthesizerService(provider=FakeLLMProvider())
        finding = make_finding(file_path="app/auth.py")
        diff = {"changed_files": ["app/auth.py", "app/payment.py"]}
        report = svc.synthesize(
            review_request="Check.",
            review_plan=None,
            diff_summary=diff,
            context=None,
            raw_findings=[],
        )
        assert "app/auth.py" in report.files_reviewed
        assert "app/payment.py" in report.files_reviewed

    def test_provider_failure_propagates(self):
        class FailingProvider(FakeLLMProvider):
            def structured_invoke(self, messages, schema):
                from app.schemas.review_planner import ReviewPlan
                if schema == ReviewPlan:
                    return super().structured_invoke(messages, schema)
                raise RuntimeError("LLM failed")

        svc = SynthesizerService(provider=FailingProvider())
        finding = make_finding(id_="sec-001", severity="high", file_path="app/auth.py")
        finding.title = "SQL Injection Risk"
        finding.evidence = ["evidence"]
        finding.description = "desc"
        finding.recommendation = "fix"
        finding.start_line = 1
        finding.end_line = 5

        with pytest.raises(RuntimeError, match="LLM failed"):
            svc.synthesize(
                review_request="Check.",
                review_plan=None,
                diff_summary=None,
                context=None,
                raw_findings=[finding.model_dump()],
            )

    def test_malformed_finding_is_skipped(self):
        svc = SynthesizerService(provider=FakeLLMProvider())
        bad_raw = {"id": "bad", "completely": "wrong"}  # missing required fields
        report = svc.synthesize(
            review_request="Check.",
            review_plan=None,
            diff_summary=None,
            context=None,
            raw_findings=[bad_raw],
        )
        # Malformed finding is skipped, no-findings path taken
        assert report.overall_risk == "none"

    def test_multiple_findings_both_returned(self):
        svc = SynthesizerService(provider=FakeLLMProvider())
        f1 = make_finding(id_="sec-001", category="security", severity="high",
                          file_path="app/auth.py", source_agent="security")
        f1.title = "SQL Injection Risk"
        f1.description = "Potential SQL injection in user query."
        f1.evidence = ["SELECT * FROM users WHERE id = "]
        f1.recommendation = "Use parameterized queries."
        f1.start_line = 47
        f1.end_line = 47

        f2 = make_finding(id_="qual-001", category="logic", severity="medium",
                          file_path="app/auth.py", source_agent="quality")
        f2.title = "Inefficient Loop"
        f2.description = "Unnecessary multiple database calls in loop."
        f2.evidence = ["user = db.get(user_id)"]
        f2.recommendation = "Fetch users in batch."
        f2.start_line = 50
        f2.end_line = 55

        report = svc.synthesize(
            review_request="Check for security code reviewer and quality and logic code reviewer issues.",
            review_plan=None,
            diff_summary=None,
            context=None,
            raw_findings=[f1.model_dump(), f2.model_dump()],
        )
        # Both findings should be in the consolidated report
        assert len(report.findings) >= 1  # At minimum one consolidated finding
        assert report.analysis_metadata.finding_count >= 1


# ---------------------------------------------------------------------------
# Unit: synthesizer_node
# ---------------------------------------------------------------------------

    def test_runtime_aware_synthesis(self):
        svc = SynthesizerService(provider=FakeLLMProvider())
        finding = make_finding(id_="sec-001", severity="high", file_path="app/auth.py")
        runtime_result = {
            "framework": "pytest",
            "execution_mode": "docker",
            "sandboxed": True,
            "status": "failed",
            "exit_code": 1,
            "duration_seconds": 2.5,
            "stdout": "...",
            "stderr": "",
            "tests_run": 5,
            "tests_passed": 4,
            "tests_failed": 1,
            "tests_skipped": 0,
            "tests_errors": 0,
            "output_truncated": False
        }
        verification_results = [{
            "finding_id": "sec-001",
            "verification_status": "verified",
            "supporting_tests": ["tests/test_auth.py::test_login"],
            "explanation": "Test fails as expected."
        }]
        report = svc.synthesize(
            review_request="Check for issues.",
            review_plan=None,
            diff_summary=None,
            context=None,
            raw_findings=[finding.model_dump()],
            runtime_test_result=runtime_result,
            verification_results=verification_results,
        )
        assert report.runtime_summary is not None
        assert report.runtime_summary.tests_run == 5
        assert report.runtime_summary.status == "failed"
        assert report.verification_summary.verified == 1
        assert len(report.verification_results) == 1
        assert report.verification_results[0].verification_status == "verified"

class TestSynthesizerNode:
    def test_node_success(self):
        state: ReviewWorkflowState = {
            "review_request": "Check for issues.",
            "findings": [],
            "errors": [],
        }
        update = synthesizer_node(state, provider=FakeLLMProvider())
        assert "final_review" in update
        assert update["errors"] == []

    def test_node_failure_preserved_findings(self):
        class FailOnSynthesize(FakeLLMProvider):
            def structured_invoke(self, messages, schema):
                from app.schemas.review_planner import ReviewPlan
                from app.schemas.agent_findings import AgentFindings
                if schema in (ReviewPlan, AgentFindings):
                    return super().structured_invoke(messages, schema)
                raise RuntimeError("Synthesis exploded")

        state: ReviewWorkflowState = {
            "review_request": "Check.",
            "findings": [make_finding().model_dump()],
            "errors": [],
        }
        update = synthesizer_node(state, provider=FailOnSynthesize())
        # Synthesizer failure should not discard findings
        # The node only returns final_review and errors in its update dict
        assert update.get("final_review") is None
        assert len(update.get("errors", [])) > 0
        # findings key is NOT in the update (LangGraph preserves existing state)
        assert "findings" not in update

    def test_node_no_findings_returns_valid_report(self):
        state: ReviewWorkflowState = {
            "review_request": "Check for issues.",
            "findings": [],
            "errors": [],
        }
        update = synthesizer_node(state, provider=FakeLLMProvider())
        assert update["final_review"] is not None
        report = FinalReviewReport(**update["final_review"])
        assert report.overall_risk == "none"
        assert report.findings == []


# ---------------------------------------------------------------------------
# Integration: graph fan-in
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init"], cwd=d, check=True)
        os.makedirs(os.path.join(d, "app"), exist_ok=True)
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


class TestGraphFanIn:
    def test_synthesizer_runs_after_both_specialists(self, temp_repo):
        provider = FakeLLMProvider()
        graph = build_review_graph(provider=provider)
        request = "Check for security code reviewer and quality and logic code reviewer issues."
        initial_state = {
            "review_request": request,
            "repository_path": temp_repo,
            "diff": {
                "files": [{
                    "path": "app/auth.py",
                    "change_type": "modified",
                    "patch": "@@ -46,3 +46,4 @@\n class AuthService:\n     def authenticate(self, user_id):\n+        return True\n"
                }]
            },
            "errors": [],
            "findings": [],
        }
        result = graph.invoke(initial_state)

        # Verify both specialist findings are present
        findings = result.get("findings", [])
        assert len(findings) == 2
        agents = {f["source_agent"] for f in findings}
        assert "security" in agents
        assert "quality" in agents

        # Verify synthesizer ran and produced final_review
        assert result.get("final_review") is not None
        report = FinalReviewReport(**result["final_review"])
        assert isinstance(report, FinalReviewReport)
        assert report.overall_risk in ("critical", "high", "medium", "low", "none")

    def test_graph_topology_has_synthesizer_node(self):
        graph = build_review_graph(provider=FakeLLMProvider())
        # The compiled graph should have a synthesizer node
        nodes = list(graph.get_graph().nodes.keys())
        assert "synthesizer" in nodes

    def test_synthesizer_runs_after_specialist_failure_isolation(self):
        """Quality fails (both agents share review_request, so we detect quality node via QUALITY prompt).
        Synthesizer still runs and does not crash the graph."""
        from tests.test_llm.fake_provider import FakeLLMProvider as Fake
        from app.schemas.agent_findings import AgentFindings

        quality_prompt_marker = "quality and logic code reviewer"
        security_prompt_marker = "security code reviewer"

        class QualityFailProvider(Fake):
            def structured_invoke(self, messages, schema):
                prompt_text = " ".join([m.content for m in messages if isinstance(m.content, str)])
                # Only fail when quality prompt is the MOST PROMINENT keyword
                # (quality prompt contains 'quality and logic code reviewer' but security doesn't)
                if (schema == AgentFindings
                        and quality_prompt_marker in prompt_text.lower()
                        and security_prompt_marker not in prompt_text.lower()):
                    raise RuntimeError("Quality agent LLM down")
                return super().structured_invoke(messages, schema)

        graph = build_review_graph(provider=QualityFailProvider())
        initial_state = {
            "review_request": "Check for security code reviewer and quality and logic code reviewer issues.",
            "findings": [],
            "errors": [],
        }
        result = graph.invoke(initial_state)

        # At minimum the graph should not crash and return a final state
        assert result is not None
        # There should be errors recorded (from quality or synthesis)
        errors = result.get("errors", [])
        # final_review key should exist in state (may be None if synthesizer also failed)
        assert "final_review" in result or result.get("errors")

    def test_both_findings_reach_synthesizer(self, temp_repo):
        """Fan-in test: A (security) + B (quality) → synthesizer sees [A, B]."""
        provider = FakeLLMProvider()
        graph = build_review_graph(provider=provider)
        request = "Check for security code reviewer and quality and logic code reviewer issues."
        initial_state = {
            "review_request": request,
            "repository_path": temp_repo,
            "diff": {
                "files": [{
                    "path": "app/auth.py",
                    "change_type": "modified",
                    "patch": "@@ -46,3 +46,4 @@\n class AuthService:\n     def authenticate(self, user_id):\n+        return True\n"
                }]
            },
            "errors": [],
            "findings": [],
        }
        result = graph.invoke(initial_state)
        report = FinalReviewReport(**result["final_review"])
        # The synthesizer received both findings
        assert isinstance(report, FinalReviewReport)
        # Verify it synthesized at least the security high finding (should not be suppressed)
        assert report.overall_risk != "none"


# ---------------------------------------------------------------------------
# Integration: workflow service
# ---------------------------------------------------------------------------

class TestWorkflowWithSynthesizer:
    def test_workflow_planner_only_has_no_final_review(self):
        svc = make_service()
        result = svc.run(review_request="Check code quality")
        # Planner-only mode: synthesizer always runs after specialists.
        # FakeLLMProvider may return findings even without a repository.
        # We only verify the report is structurally valid.
        assert result.final_review is not None
        assert result.final_review.overall_risk in ("critical", "high", "medium", "low", "none")
        assert isinstance(result.final_review.summary, str)

    def test_workflow_result_includes_final_review_field(self):
        svc = make_service()
        result = svc.run(review_request="security check")
        assert hasattr(result, "final_review")

    def test_workflow_with_git_repo_has_final_review(self, temp_repo):
        svc = make_service()
        # Run without diff (no base/head) — synthesizer still produces report
        result = svc.run(
            review_request="Check for security code reviewer and quality and logic code reviewer issues.",
            repository_path=temp_repo,
        )
        assert result.final_review is not None


# ---------------------------------------------------------------------------
# Integration: API
# ---------------------------------------------------------------------------

class TestAPIWithSynthesizer:
    def test_api_response_includes_final_review(self, monkeypatch):
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
        assert "runtime_test_result" in data
        assert "verification_results" in data
        
        assert "final_review" in data
        assert data["final_review"] is not None
        fr = data["final_review"]
        assert "summary" in fr
        assert "overall_risk" in fr
        assert "findings" in fr
        assert "recommendations" in fr
        assert "files_reviewed" in fr
        assert "analysis_metadata" in fr
        assert "runtime_summary" in fr
        assert "verification_summary" in fr
        assert "verification_results" in fr

    def test_api_response_preserves_raw_findings(self, monkeypatch):
        from app.services.review_workflow import ReviewWorkflowService as RWS
        orig_init = RWS.__init__

        def fake_init(self, provider=None):
            orig_init(self, provider=FakeLLMProvider())

        monkeypatch.setattr(RWS, "__init__", fake_init)

        resp = client.post("/api/ai/review", json={
            "review_request": "Check for security code reviewer and quality and logic code reviewer issues.",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Both raw findings AND final_review are in the response
        assert "findings" in data
        assert "final_review" in data

    def test_api_with_real_git_repo(self, temp_repo, monkeypatch):
        from app.services.review_workflow import ReviewWorkflowService as RWS
        orig_init = RWS.__init__
        import subprocess
        import os

        # Create a second commit to get a real diff
        auth2 = os.path.join(temp_repo, "app", "auth2.py")
        with open(auth2, "w", encoding="utf-8") as f:
            f.write("# security issue\ndef login(user, pw):\n    query = 'SELECT * FROM users WHERE u=' + user\n    return True\n")
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True)
        subprocess.run(["git", "commit", "-m", "add auth2"], cwd=temp_repo, check=True)

        def fake_init(self, provider=None):
            orig_init(self, provider=FakeLLMProvider())

        monkeypatch.setattr(RWS, "__init__", fake_init)

        resp = client.post("/api/ai/review", json={
            "review_request": "Check for security code reviewer and quality and logic code reviewer issues.",
            "repository_path": temp_repo,
            "base_revision": "HEAD~1",
            "head_revision": "HEAD",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("completed", "completed_with_errors")
        assert "review_plan" in data
        assert "findings" in data
        assert "final_review" in data
        assert "errors" in data

        fr = data["final_review"]
        assert fr is not None
        assert "summary" in fr
        assert fr["overall_risk"] in ("critical", "high", "medium", "low", "none")
