from abc import ABC, abstractmethod
from typing import Type, TypeVar
from pydantic import BaseModel
from langchain_core.messages import BaseMessage

T = TypeVar('T', bound=BaseModel)

class LLMProvider(ABC):
    """
    Abstract interface for LLM providers.
    Ensures higher-level agents don't depend on specific provider implementations.
    """
    
    @abstractmethod
    def invoke(self, messages: list[BaseMessage]) -> BaseMessage:
        """Invoke the LLM with a list of messages."""
        pass
        
    @abstractmethod
    def structured_invoke(self, messages: list[BaseMessage], schema: Type[T]) -> T:
        """Invoke the LLM and force output to match the given Pydantic schema."""
        pass
