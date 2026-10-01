from typing import Type, TypeVar
from pydantic import BaseModel
from langchain_core.messages import BaseMessage, AIMessage
from app.services.llm.interface import LLMProvider
from app.schemas.review_planner import ReviewPlan

T = TypeVar('T', bound=BaseModel)

class FakeLLMProvider(LLMProvider):
    def invoke(self, messages: list[BaseMessage]) -> BaseMessage:
        return AIMessage(content="Deterministic fake response")
        
    def structured_invoke(self, messages: list[BaseMessage], schema: Type[T]) -> T:
        if schema == ReviewPlan:
            # Return a deterministic test object
            return schema(
                scope=["security", "logic"],
                priority="high",
                reason="Authentication behavior changed.",
                required_context=["changed function", "callers", "authentication implementation"]
            )
        raise ValueError(f"FakeLLMProvider does not support schema {schema.__name__}")
