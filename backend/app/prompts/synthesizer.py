"""
Synthesizer prompts.

System role: senior code review editor.
The synthesizer consolidates specialist findings into a coherent final report.
It must NOT invent new findings, file paths, or repository facts.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

SYNTHESIZER_SYSTEM_PROMPT = """\
You are a senior code review editor.

Your job is to consolidate structured findings produced by specialist agents \
and runtime verification evidence into a coherent, developer-facing final review report.

Rules:
1. Static findings come from specialist agents.
2. Runtime evidence comes from deterministic tests.
3. Verification results describe support/contradiction/inconclusiveness.
4. Do not invent test results.
5. Do not upgrade severity merely because a test failed.
6. Do not downgrade a finding merely because tests passed.
7. Passing tests do not prove absence of security/performance issues.
8. Failed tests only support a finding when the evidence is relevant.
9. Preserve finding IDs.
10. Preserve evidence provenance.
11. Do not create new findings.
12. Do not invent supporting tests.
13. Do not invent files, functions, line numbers, or behaviors.
14. Return structured output only.
15. Do not output hidden chain-of-thought.
16. Deduplicate overlapping findings. Preserve the higher severity and all evidence.
17. The summary must be concise and factual. Do not include unsupported claims.
18. Generate actionable recommendations based ONLY on the supplied findings.
"""


def build_synthesizer_messages(
    review_request: str,
    review_plan: Optional[Dict[str, Any]],
    diff_summary: Optional[Dict[str, Any]],
    context: Optional[Dict[str, Any]],
    findings: List[Dict[str, Any]],
    files_reviewed: List[str],
    runtime_summary: Optional[Dict[str, Any]] = None,
    verification_summary: Optional[Dict[str, Any]] = None,
    verification_results: Optional[List[Dict[str, Any]]] = None,
) -> list:
    """
    Construct the LangChain message list for the synthesizer.

    Context is deliberately bounded:
    - diff_summary: only top-level statistics + file names (no raw patches)
    - context: passed as-is from the context agent (already bounded by limits)
    - findings: full specialist findings (these are the primary input)
    - files_reviewed: deterministic list, not computed by the LLM
    """
    messages = [SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT)]

    parts: List[str] = []
    parts.append(f"## Review Request\n{review_request}\n")

    if review_plan:
        parts.append(
            f"## Review Plan\n"
            f"Scope: {review_plan.get('scope', [])}\n"
            f"Priority: {review_plan.get('priority', 'unknown')}\n"
            f"Reason: {review_plan.get('reason', '')}\n"
        )

    if diff_summary:
        # Only include file names and counts — do NOT include raw patch text
        safe_diff = {
            "changed_files": diff_summary.get("changed_files", []),
            "total_additions": diff_summary.get("total_additions", 0),
            "total_deletions": diff_summary.get("total_deletions", 0),
        }
        parts.append(f"## Diff Summary\n{json.dumps(safe_diff, indent=2)}\n")

    parts.append(f"## Files Reviewed\n{json.dumps(files_reviewed)}\n")

    if context:
        # Bounded context: only changed_files, changed_symbols, related_files
        safe_context = {
            "changed_files": context.get("changed_files", []),
            "changed_symbols": context.get("changed_symbols", []),
            "related_files": context.get("related_files", []),
        }
        parts.append(f"## Repository Context\n{json.dumps(safe_context, indent=2)}\n")

    parts.append(
        f"## Specialist Findings\n"
        f"Total findings: {len(findings)}\n"
        f"{json.dumps(findings, indent=2)}\n"
    )

    if runtime_summary:
        parts.append(f"## Runtime Summary\n{json.dumps(runtime_summary, indent=2)}\n")

    if verification_summary:
        parts.append(f"## Verification Summary\n{json.dumps(verification_summary, indent=2)}\n")

    if verification_results:
        parts.append(f"## Verification Results\n{json.dumps(verification_results, indent=2)}\n")

    parts.append(
        "## Task\n"
        "Produce a consolidated FinalReviewReport from the findings above.\n"
        "Deduplicate overlapping findings. Preserve all non-overlapping findings.\n"
        "Generate recommendations based only on the preserved findings.\n"
        "The summary should be 1-2 sentences describing the overall review outcome.\n"
    )

    messages.append(HumanMessage(content="\n".join(parts)))
    return messages
