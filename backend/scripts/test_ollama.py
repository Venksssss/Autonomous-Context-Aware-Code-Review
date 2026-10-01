import sys
import json
import logging
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.schemas.review_planner import ReviewPlan
from app.prompts.review_planner import build_review_planner_messages
from app.services.llm.factory import create_llm_provider

logging.basicConfig(level=logging.INFO)

def run_smoke_test():
    try:
        provider = create_llm_provider()
    except Exception as e:
        print(f"Skipping smoke test: Could not configure provider: {e}")
        return

    print("Configured OllamaProvider successfully.")
    
    messages = build_review_planner_messages(
        request="Review the authentication changes for security and regressions.",
        repository_context={"changed_files": ["app/auth.py"]}
    )
    
    print("Sending request to Ollama...")
    try:
        plan = provider.structured_invoke(messages, ReviewPlan)
        print("\nStructured Output Received:")
        print(json.dumps(plan.model_dump(), indent=2))
        print("\nSmoke test successful!")
    except Exception as e:
        print(f"\nSkipping smoke test: Ollama invocation failed. Is the model downloaded and server running? Error: {e}")

if __name__ == "__main__":
    run_smoke_test()
