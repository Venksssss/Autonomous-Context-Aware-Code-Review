import pytest
from app.services.llm.factory import create_llm_provider
from app.config import settings

def test_factory_ollama(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_model", "fake-model")
    
    provider = create_llm_provider()
    from app.services.llm.ollama_provider import OllamaProvider
    assert isinstance(provider, OllamaProvider)

def test_factory_unsupported(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "unsupported-llm")
    
    with pytest.raises(ValueError) as exc:
        create_llm_provider()
    assert "LLM_PROVIDER_UNSUPPORTED" in str(exc.value)

def test_ollama_missing_model_config(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "ollama_model", None)
    
    with pytest.raises(ValueError) as exc:
        create_llm_provider()
    assert "LLM_CONFIGURATION_INVALID" in str(exc.value)
