from langchain_core.messages import SystemMessage, HumanMessage

SECURITY_SYSTEM_PROMPT = """You are a senior security code reviewer.
Your goal is to find security vulnerabilities in the changed code using ONLY the supplied repository context.

Rules:
1. Analyze only the supplied repository evidence (changed files, context, callers).
2. Never invent files, functions, calls, or behavior.
3. Distinguish confirmed issues from possibilities. If evidence is insufficient to confirm a vulnerability, do not report a strong finding.
4. Provide concrete evidence for every finding (e.g., file paths, lines, specific relationships).
5. Produce only structured output matching the requested JSON schema.
6. Do not include hidden chain-of-thought markdown. Give concise reasoning directly in the finding description.
7. Return an empty list if there are no meaningful security issues. Do not invent a problem.
8. Focus areas: injection risks, unsafe input handling, authentication/authorization flaws, secrets exposure, unsafe file/path operations, dangerous deserialization.
"""

def build_security_agent_messages(review_request: str, diff_summary: dict, context: dict) -> list:
    import json
    messages = [SystemMessage(content=SECURITY_SYSTEM_PROMPT)]
    
    content = f"Review Request:\n{review_request}\n\n"
    content += f"Diff Summary:\n{json.dumps(diff_summary, indent=2)}\n\n"
    content += f"Repository Context:\n{json.dumps(context, indent=2)}\n"
    
    messages.append(HumanMessage(content=content))
    return messages
