from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    host: str = "0.0.0.0"
    port: int = 8000

    # LLM Settings
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: Optional[str] = None
    llm_temperature: float = 0.0
    llm_timeout: float = 60.0

    # Docker Sandbox Settings
    docker_sandbox_enabled: bool = False
    docker_image: str = "python:3.12-slim"
    docker_cpu_limit: float = 1.0
    docker_memory_limit: str = "512m"
    docker_pids_limit: int = 128
    docker_timeout_seconds: int = 60
    docker_output_limit: int = 50000


settings = Settings()
