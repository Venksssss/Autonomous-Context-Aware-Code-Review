import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.review_planner import ReviewPlannerService
from tests.test_llm.fake_provider import FakeLLMProvider

client = TestClient(app)

def test_planner_service_with_fake_provider():
    provider = FakeLLMProvider()
    service = ReviewPlannerService(provider=provider)
    
    plan = service.generate_plan("Test request")
    
    assert plan.priority == "high"
    assert "security" in plan.scope
    assert "Authentication behavior changed." in plan.reason

def test_api_review_plan_with_fake_provider(monkeypatch):
    # We monkeypatch the constructor to always use FakeLLMProvider
    original_init = ReviewPlannerService.__init__
    
    def fake_init(self, provider=None):
        original_init(self, provider=FakeLLMProvider())
        
    monkeypatch.setattr(ReviewPlannerService, "__init__", fake_init)
    
    response = client.post("/api/ai/review-plan", json={
        "request": "Review the authentication changes for security and regressions.",
        "repository_context": {
            "changed_files": ["app/auth.py"]
        }
    })
    
    assert response.status_code == 200
    data = response.json()
    assert data["priority"] == "high"
    assert "security" in data["scope"]
    assert "changed function" in data["required_context"]

def test_api_review_plan_handles_config_error(monkeypatch):
    def fail_factory():
        raise ValueError("LLM_CONFIGURATION_INVALID")
        
    monkeypatch.setattr("app.services.review_planner.create_llm_provider", fail_factory)
    
    response = client.post("/api/ai/review-plan", json={"request": "Test"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "LLM_CONFIGURATION_ERROR"

def test_api_review_plan_handles_invocation_error(monkeypatch):
    class FailingProvider(FakeLLMProvider):
        def structured_invoke(self, messages, schema):
            raise RuntimeError("LLM_STRUCTURED_OUTPUT_FAILED")
            
    original_init = ReviewPlannerService.__init__
    
    def fake_init(self, provider=None):
        original_init(self, provider=FailingProvider())
        
    monkeypatch.setattr("app.services.review_planner.ReviewPlannerService.__init__", fake_init)
    
    response = client.post("/api/ai/review-plan", json={"request": "Test"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "LLM_INVOCATION_ERROR"
