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
        
        # Avoid circular imports by importing locally
        from app.schemas.agent_findings import AgentFindings, Finding
        if schema == AgentFindings:
            # Determine which finding to return based on the messages content
            prompt_text = " ".join([m.content for m in messages if isinstance(m.content, str)])
            
            if "security code reviewer" in prompt_text.lower():
                return schema(findings=[
                    Finding(
                        id="sec-001",
                        category="security",
                        severity="high",
                        title="SQL Injection Risk",
                        description="Potential SQL injection in user query.",
                        file_path="app/auth.py",
                        start_line=47,
                        end_line=47,
                        evidence=["SELECT * FROM users WHERE id = "],
                        recommendation="Use parameterized queries.",
                        confidence=0.9,
                        source_agent="security"
                    )
                ])
            elif "quality and logic code reviewer" in prompt_text.lower():
                return schema(findings=[
                    Finding(
                        id="qual-001",
                        category="logic",
                        severity="medium",
                        title="Inefficient Loop",
                        description="Unnecessary multiple database calls in loop.",
                        file_path="app/auth.py",
                        start_line=50,
                        end_line=55,
                        evidence=["user = db.get(user_id)"],
                        recommendation="Fetch users in batch.",
                        confidence=0.9,
                        source_agent="quality"
                    )
                ])
            else:
                return schema(findings=[])

        # Handle synthesizer output schema
        from app.services.review_agents.synthesizer import _SynthesizerLLMOutput
        from app.schemas.agent_findings import Finding
        if schema == _SynthesizerLLMOutput:
            prompt_text = " ".join([m.content for m in messages if isinstance(m.content, str)])
            # Extract findings passed in the prompt to return them consolidated
            # The fake synthesizer just echoes findings and adds a summary
            has_security = "SQL Injection" in prompt_text or "sec-001" in prompt_text
            has_quality = "Inefficient Loop" in prompt_text or "qual-001" in prompt_text

            consolidated: list = []
            if has_security:
                consolidated.append(Finding(
                    id="sec-001",
                    category="security",
                    severity="high",
                    title="SQL Injection Risk",
                    description="Potential SQL injection in user query.",
                    file_path="app/auth.py",
                    start_line=47,
                    end_line=47,
                    evidence=["SELECT * FROM users WHERE id = "],
                    recommendation="Use parameterized queries.",
                    confidence=0.9,
                    source_agent="security"
                ))
            if has_quality:
                consolidated.append(Finding(
                    id="qual-001",
                    category="logic",
                    severity="medium",
                    title="Inefficient Loop",
                    description="Unnecessary multiple database calls in loop.",
                    file_path="app/auth.py",
                    start_line=50,
                    end_line=55,
                    evidence=["user = db.get(user_id)"],
                    recommendation="Fetch users in batch.",
                    confidence=0.9,
                    source_agent="quality"
                ))

            if consolidated:
                count = len(consolidated)
                summary = (
                    f"Review identified {count} actionable issue(s): "
                    + ", ".join(f.title for f in consolidated) + "."
                )
                recommendations = [f.recommendation for f in consolidated]
            else:
                summary = "No actionable issues were identified in the reviewed changes."
                recommendations = []

            return schema(
                summary=summary,
                findings=consolidated,
                recommendations=recommendations,
            )

        raise ValueError(f"FakeLLMProvider does not support schema {schema.__name__}")
