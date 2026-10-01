from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    
    # LLM Settings
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: Optional[str] = None
    llm_temperature: float = 0.0
    llm_timeout: float = 60.0
    
    class Config:
        env_file = ".env"

settings = Settings()
