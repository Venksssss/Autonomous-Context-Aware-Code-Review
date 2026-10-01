import logging
from typing import Type, TypeVar
from pydantic import BaseModel
from langchain_core.messages import BaseMessage
from langchain_ollama import ChatOllama

from app.services.llm.interface import LLMProvider
from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class OllamaProvider(LLMProvider):
    def __init__(self):
        if not settings.ollama_model:
            raise ValueError("LLM_CONFIGURATION_INVALID: OLLAMA_MODEL must be configured when using Ollama provider.")
            
        self.llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=settings.llm_temperature,
        )
        logger.info(f"Initialized OllamaProvider with model={settings.ollama_model}")
        
    def invoke(self, messages: list[BaseMessage]) -> BaseMessage:
        try:
            logger.info("Invoking Ollama LLM")
            return self.llm.invoke(messages)
        except Exception as e:
            logger.error(f"Ollama invocation failed: {str(e)}")
            raise RuntimeError(f"LLM_INVOCATION_FAILED: {str(e)}")
            
    def structured_invoke(self, messages: list[BaseMessage], schema: Type[T]) -> T:
        try:
            logger.info(f"Invoking Ollama LLM with structured output schema={schema.__name__}")
            structured_llm = self.llm.with_structured_output(schema)
            return structured_llm.invoke(messages)
        except Exception as e:
            logger.error(f"Ollama structured invocation failed: {str(e)}")
            raise RuntimeError(f"LLM_STRUCTURED_OUTPUT_FAILED: {str(e)}")
