from app.config import settings
from app.services.llm.interface import LLMProvider

def create_llm_provider() -> LLMProvider:
    provider = settings.llm_provider.lower()
    
    if provider == "ollama":
        from app.services.llm.ollama_provider import OllamaProvider
        return OllamaProvider()
    else:
        raise ValueError(f"LLM_PROVIDER_UNSUPPORTED: Provider '{provider}' is not supported.")
