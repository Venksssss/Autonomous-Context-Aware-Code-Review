from langchain_core.messages import SystemMessage, HumanMessage

PLANNER_SYSTEM_PROMPT = """You are a senior software-engineering review planner.
Your goal is to analyze a code review request and determine the scope, priority, and required context to execute it successfully.

You must return a structured response containing:
- scope: A list of review dimensions relevant to the request (e.g. security, logic, performance, best practices).
- priority: One of 'low', 'medium', 'high'.
- reason: A concise reason explaining your assessment.
- required_context: A list of specific repository artifacts (files, functions, callers, implementations) you need to perform the review.

IMPORTANT: Do not invent repository facts. If sufficient repository evidence is not supplied, you must state what context is required instead of pretending you know it.
"""

def build_review_planner_messages(request: str, repository_context: dict = None) -> list:
    messages = [SystemMessage(content=PLANNER_SYSTEM_PROMPT)]
    
    content = f"Review Request:\n{request}\n"
    if repository_context:
        import json
        content += f"\nProvided Context:\n{json.dumps(repository_context, indent=2)}"
    else:
        content += "\nProvided Context: None"
        
    messages.append(HumanMessage(content=content))
    return messages
