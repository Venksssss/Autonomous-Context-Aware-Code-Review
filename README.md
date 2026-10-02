# Autonomous Context-Aware Code Review

## Project Overview
This project aims to build an autonomous context-aware code review system. It will incrementally analyze a Git repository, extract context, and use advanced tools to review code changes intelligently.

### Problem Being Solved
Standard code reviews often lack deep context about the entire project architecture, leading to missed regressions or architectural violations. This system will ingest the whole repository context to provide high-quality autonomous reviews.

## Current Implementation Status
**Phase 1 — Segment 1**

*Note: Current segment performs deterministic Git repository inspection only. Do NOT claim that AI agents, RAG, AST parsing, GraphRAG, MCP, testing sandbox, or code review analysis are already implemented.*

### Architecture & Project Structure
```
autonomous-code-review
│
├── backend
│   ├── app
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── api/routes
│   │   ├── services
│   │   └── schemas
│   ├── tests
│   ├── requirements.txt
│   └── .env.example
├── .gitignore
└── README.md
```

### Tech Stack
- Python 3.11+
- FastAPI
- Uvicorn
- Pydantic
- Git CLI (via subprocess)
- pytest
- python-dotenv

## Prerequisites
- Python 3.11+
- Git installed and available in system PATH

## Installation

1. **Clone the repository** (or initialize it):
   ```bash
   git clone https://github.com/Venksssss/Autonomous-Context-Aware-Code-Review.git
   cd Autonomous-Context-Aware-Code-Review
   ```

2. **Virtual environment setup**:
   ```bash
   cd backend
   python -m venv .venv
   
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Dependency installation**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment configuration**:
   ```bash
   cp .env.example .env
   ```

## How to run FastAPI

From the `backend` directory, run:
```bash
uvicorn app.main:app --reload
```

- **Swagger URL**: http://127.0.0.1:8000/docs
- **Health endpoint**: http://127.0.0.1:8000/health
- **Repository inspection endpoint**: `GET /api/repositories/inspect?repository_path=/path/to/repo`
- **Diff extraction endpoint**: `POST /api/repositories/diff`

### Diff Extraction API
This endpoint compares two Git revisions and returns a structured representation of the code changes.
- `base_revision`: The starting Git revision (e.g., `main`, `HEAD~1`, or a commit SHA)
- `head_revision`: The ending Git revision (e.g., `feature/branch`, `HEAD`, or a commit SHA)

**Example Request**:
```json
{
    "repository_path": "C:\\Projects\\myrepo",
    "base_revision": "HEAD~1",
    "head_revision": "HEAD"
}
```

**Example Response**:
```json
{
    "repository": "C:\\Projects\\myrepo",
    "base_revision": "HEAD~1",
    "head_revision": "HEAD",
    "files_changed": 1,
    "files": [
        {
            "path": "app/auth.py",
            "change_type": "modified",
            "additions": 4,
            "deletions": 2,
            "patch": "diff --git a/app/auth.py b/app/auth.py\n..."
        }
    ]
}
```
*Supported change types:* `added`, `modified`, `deleted`, `renamed`, `copied`, `unknown`.

## How to run tests
From the `backend` directory, run:
```bash
pytest -v
```

## Current limitations
- Currently, it only inspects a local filesystem path and extracts Git diffs deterministically.
- Does not decode binary file diffs as text.

## Phase 2 — Semantic Repository Understanding

### Segment 1: Tree-sitter Foundation
Phase 2 Segment 1 introduces deterministic, semantic source code parsing using **Tree-sitter**.
Unlike text-based diffing or regex searching, AST (Abstract Syntax Tree) parsing natively understands source code structures like functions, classes, and statements. Tree-sitter is incredibly fast, error-tolerant, and allows deterministic parsing.

**Current Supported Language**: Python

**Code Parsing Endpoint**: `POST /api/code/parse`
This endpoint parses a specified file in the given repository and returns structural metadata.

**Example Request**:
```json
{
    "repository_path": "C:\\Projects\\myrepo",
    "file_path": "app/auth.py"
}
```

**Example Response**:
```json
{
    "path": "app/auth.py",
    "language": "python",
    "parsed": true,
    "has_errors": false,
    "root_node_type": "module",
    "error_count": 0
}
```
*Note: Segment 1 focuses on parse validation only — symbol extraction is Segment 2.*

### Segment 2: AST Symbol and Reference Extraction

Phase 2 Segment 2 walks the Tree-sitter syntax tree produced in Segment 1 and
deterministically extracts structured code intelligence from individual Python files.

**Architecture**

```
Tree-sitter parse (Segment 1)
    |
    v
Syntax Tree (in-memory)
    |
    v
CodeAnalyzerService — AST traversal
    |
    +-- Symbols (classes / functions / methods, qualified names, source locations)
    +-- Imports (import X / from X import Y / import X as Y)
    +-- Calls   (syntactic call sites, not yet resolved cross-file)
```

**Extracted information per file**

| Kind | Examples |
|---|---|
| Class | `PaymentService` |
| Function | `helper` |
| Method | `PaymentService.process` |
| Parameters | `["self", "user"]` |
| Import | `import os`, `import numpy as np` |
| From-import | `from app.auth import verify_token` |
| Call site | `verify_token(user)`, `charge(token)` |

All line numbers are **1-based**. Qualified names use dot-notation (`Outer.Inner.method`).

**Code Analysis Endpoint**: `POST /api/code/analyze`

**Example Request**:
```json
{
    "repository_path": "C:\\Projects\\myrepo",
    "file_path": "app/payment.py"
}
```

**Example Response**:
```json
{
  "file_path": "app/payment.py",
  "language": "python",
  "symbols": [
    {
      "name": "PaymentService",
      "qualified_name": "PaymentService",
      "symbol_type": "class",
      "file_path": "app/payment.py",
      "start_line": 3,
      "end_line": 7,
      "start_column": 0,
      "end_column": 28,
      "parent": null,
      "parameters": null
    },
    {
      "name": "process",
      "qualified_name": "PaymentService.process",
      "symbol_type": "method",
      "file_path": "app/payment.py",
      "start_line": 5,
      "end_line": 7,
      "start_column": 4,
      "end_column": 28,
      "parent": "PaymentService",
      "parameters": ["self", "user"]
    }
  ],
  "imports": [
    { "module": "app.auth", "name": "verify_token", "alias": null, "line": 1 }
  ],
  "calls": [
    { "name": "verify_token", "line": 6, "column": 16, "kind": "call" },
    { "name": "charge",       "line": 7, "column": 15, "kind": "call" }
  ],
  "has_errors": false,
  "error_count": 0
}
```

**What Segment 2 does NOT do (by design)**

- Cross-file symbol resolution — `verify_token` is recorded syntactically but not linked to its definition in `app/auth.py`
- Call graph construction
- Dependency graph
- Repository-wide indexing
- Any LLM inference

### Segment 3: Repository-wide Semantic Model

Segment 3 converts the per-file structural analysis from Segment 2 into a deterministic, repository-wide knowledge graph.

**Architecture Pipeline**
```
Files
 ↓
Tree-sitter
 ↓
FileAnalysis
 ↓
Symbol Index
 ↓
Import Resolution
 ↓
Call Resolution
 ↓
Relationship Graph
 ↓
Context Query
```

**CALL EXTRACTION vs. CALL RESOLUTION**

It is critical to distinguish between these two:
- **CALL EXTRACTION (Segment 2)** identifies *syntactic* calls, like "this file contains a call to `verify_token()`".
- **CALL RESOLUTION (Segment 3)** attempts to map that call to a specific repository symbol, e.g., "`verify_token` defined in `app/auth.py:27`".

Segment 3 uses deterministic import mapping, module resolution, and uniqueness checks to resolve calls. If a reference cannot be deterministically resolved without type inference, it is explicitly flagged as `unresolved`. If multiple valid candidates exist (e.g. `service.process`), it is flagged as `ambiguous`.

**Symbol Identity Strategy**
Symbols are uniquely identified using: `module_name::qualified_name::file_path`
(Example: `app.payment::PaymentService.process::app/payment.py`)

**Relationship Types**
- `defines`: A file defines a symbol.
- `imports`: A file imports a symbol or module from another file.
- `calls`: A symbol invokes another resolved symbol.

**Repository Analysis API**: `POST /api/repository/analyze`
Discovers all Python files, analyzes them, and constructs the structural model.

**Context Query API**: `POST /api/repository/context`
Retrieves the structurally related context for a specific symbol (e.g. its definition, what it calls, what calls it, and its imports), which is highly valuable for providing a targeted structural view to an LLM without overwhelming it with the entire codebase.

## Phase 3 — Agentic Infrastructure

### Segment 1 — LLM Abstraction

Phase 3 introduces the foundation for LLM-based autonomous behavior, starting with a clean, provider-agnostic abstraction layer.

**LLM Architecture**
```
Application / Planner Service
    ↓
LLM Factory
    ↓
LLM Provider Interface
    ↓
Ollama (or FakeLLMProvider for tests)
```

By relying on this abstraction rather than directly importing `ChatOllama` across the codebase, the application stays highly decoupled. This allows future seamless integrations with other providers (like Gemini or OpenAI) without modifying agent logic.

**Capabilities Implemented**
- **Local Ollama Support:** Configured via environment variables (`LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `LLM_TEMPERATURE`, `LLM_TIMEOUT`). No hardcoded secrets.
- **Structured Pydantic Output:** The AI explicitly responds with strongly-typed outputs (e.g. `ReviewPlan`) rather than unpredictable raw strings.
- **Testability:** A `FakeLLMProvider` guarantees the entire test suite (now 63 tests) runs identically on any machine without requiring Ollama to be installed, running, or models to be pulled.

**AI Planning API**: `POST /api/ai/review-plan`
Accepts a natural-language review request and repository context, returning a structured review plan containing `scope`, `priority`, `reason`, and `required_context`.

**Example Request:**
```json
{
  "request": "Review the authentication changes for security and regressions.",
  "repository_context": {
    "changed_files": ["app/auth.py"],
    "changed_symbols": ["AuthService.authenticate"]
  }
}
```

**Example Response:**
```json
{
  "scope": ["security", "logic"],
  "priority": "high",
  "reason": "Authentication logic directly impacts access control.",
  "required_context": [
    "AuthService.authenticate implementation",
    "callers of authenticate"
  ]
}
```

## Next Phases
- Phase 3, Segment 2: Agents, MCP, memory, and orchestrated review pipelines.
- Phase 4: GitHub PR automation and user-facing endpoints.

### Segment 2 — LangGraph Orchestration

Segment 2 introduces LangGraph as the workflow engine, replacing ad-hoc sequential calls with a typed, state-driven pipeline.

**Why shared state?**
In a multi-agent system each specialist (context, security, quality) needs to read findings from earlier agents and contribute its own.  A shared, append-safe TypedDict state lets every node read what it needs and write only what it produces, without lock-step coupling.

**Current graph topology**
```
START → planner → END
```

**State fields (key)**
| Field | Populated by | Purpose |
|---|---|---|
| `review_request` | caller | natural-language request |
| `diff` | workflow service | raw Git diff data |
| `review_plan` | planner node | AI-produced plan |
| `findings` | future specialist agents | accumulated findings |
| `errors` | any node | error accumulation (add-reducer) |

**Why routes call WorkflowService, not LangGraph directly**
Routes must stay thin.  `ReviewWorkflowService` owns: diff retrieval (via `GitService`, not HTTP), graph construction with injected provider, and result marshalling.  LangGraph internals never leak into route handlers.

**Orchestrated Review API**: `POST /api/ai/review`
Full LangGraph-powered review workflow.

**Example Request:**
```json
{
  "review_request": "Review the authentication changes for security and regressions.",
  "repository_path": "C:\\Projects\\repo",
  "base_revision": "main",
  "head_revision": "feature/login"
}
```

**Example Response:**
```json
{
  "status": "planned",
  "review_plan": {
    "scope": ["security", "logic"],
    "priority": "high",
    "reason": "Authentication behavior changed.",
    "required_context": ["changed function", "callers", "authentication implementation"]
  },
  "errors": []
}
```

**Future segments will add** (not yet implemented):
- `context_agent` node — retrieves relevant repository graph context
- `security_agent` node — specialised security review
- `quality_agent` node — code quality review
- `synthesizer` node — merges specialist findings into final report

## Next Phases
- Phase 3, Segment 3: Specialist agents (context, security, quality) + synthesizer.
- Phase 4: GitHub PR automation and user-facing endpoints.

### Segment 3 — Multi-Agent Repository Analysis

Segment 3 transforms the linear planner pipeline into a real multi-agent analysis workflow.

**Graph Topology**
```
START → planner → context_agent
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
      security_agent        quality_agent
            │                     │
            └──────────┬──────────┘
                       ▼
                      END
```

**Agents**
1. **Context Agent**: Deterministically expands the Git diff into structural repository context (related symbols, calls, imports). It uses `RepositoryAnalyzerService` to find callers/callees. It does *not* use an LLM, ensuring facts are deterministic.
2. **Security Agent**: A specialist LLM prompt focused on finding security vulnerabilities using the supplied repository context.
3. **Quality Agent**: A specialist LLM prompt focused on finding logic defects, inefficient operations, and maintainability issues.

**Shared State and Findings Reducer**
The `findings` field in `ReviewWorkflowState` uses LangGraph's `operator.add` reducer. This allows `security_agent` and `quality_agent` to run in parallel (fan-out) and safely append their structured `Finding` objects to the state without overwriting each other.

**Finding Quality Control**
Before appending a finding to the state, the agents validate:
- The referenced file actually exists in the target repository.
- The start and end lines are within the file's valid line range.

**Final Synthesis**
*Note: The final `synthesizer` node (which merges specialist findings into a cohesive final review report) is not yet implemented.*

## Phase 3 — Segment 4: Synthesizer Agent + Final Review Report

Segment 4 adds the Synthesizer Agent as the terminal node of the review graph. It consolidates all specialist findings into a single, developer-facing `FinalReviewReport`.

### Architectural Principle

Specialist agents **find** issues. The Synthesizer **organizes** issues.

```
Security Agent  →  finding
Quality Agent   →  finding
Context Agent   →  evidence
                    ↓
              Synthesizer
                    ↓
          FinalReviewReport
```

The Synthesizer does **not** perform fresh repository exploration. It reasons only over structured state already produced by the specialist agents.

### Final Graph Topology

```
START → planner → context_agent
                       │
            ┌──────────┴──────────┐
            ▼                     ▼
      security_agent        quality_agent
            │                     │
            └──────────┬──────────┘
                       ▼
                  synthesizer
                       ▼
                      END
```

### FinalReviewReport Schema

```json
{
  "summary": "Review identified 2 actionable issues: one high-severity SQL injection and one medium-severity logic defect.",
  "overall_risk": "high",
  "findings": [...],
  "recommendations": [
    "Use parameterized queries to prevent SQL injection.",
    "Fetch users in batch to reduce database calls."
  ],
  "files_reviewed": ["app/auth.py", "app/payment.py"],
  "analysis_metadata": {
    "finding_count": 2,
    "security_findings": 1,
    "quality_findings": 1,
    "agents_used": ["planner", "context", "security", "quality", "synthesizer"]
  }
}
```

### Deduplication

The Synthesizer uses the LLM to identify overlapping findings (same file, same location, same root cause) and merge them into a single finding, preserving the higher severity and all evidence. Non-overlapping findings are always preserved.

### Severity and Risk Policy

- **Severity preservation**: The Synthesizer does not casually upgrade or downgrade individual finding severities.
- **`overall_risk` is computed deterministically** by Python (not by the LLM) using the following policy:
  - `critical` finding → overall `critical`
  - else `high` → overall `high`
  - else `medium` → overall `medium`
  - else `low`/`info` → overall `low`
  - no findings → overall `none`

### Full API Response (POST /api/ai/review)

```json
{
  "status": "completed",
  "review_plan": {
    "scope": ["security", "logic"],
    "priority": "high",
    "reason": "Authentication logic directly impacts access control.",
    "required_context": ["AuthService.authenticate", "callers"]
  },
  "findings": [
    {
      "id": "sec-001",
      "category": "security",
      "severity": "high",
      "title": "SQL Injection Risk",
      "description": "...",
      "file_path": "app/auth.py",
      "start_line": 47,
      "end_line": 47,
      "evidence": ["SELECT * FROM users WHERE id = user_id"],
      "recommendation": "Use parameterized queries.",
      "source_agent": "security"
    }
  ],
  "final_review": {
    "summary": "Review identified 1 actionable issue: a high-severity SQL injection vulnerability.",
    "overall_risk": "high",
    "findings": [...],
    "recommendations": ["Use parameterized queries to prevent SQL injection."],
    "files_reviewed": ["app/auth.py"],
    "analysis_metadata": {
      "finding_count": 1,
      "security_findings": 1,
      "quality_findings": 0,
      "agents_used": ["planner", "context", "security", "quality", "synthesizer"]
    }
  },
  "errors": []
}
```

Both raw `findings` (from specialists) and `final_review` (synthesized) are returned for transparency. Developers can compare the two to understand what the synthesizer changed in presentation versus what the specialists originally reported.

### Error Handling

- If a specialist agent fails, its findings are absent but errors are recorded. The Synthesizer still runs on whatever findings are available.
- If the Synthesizer itself fails, `final_review` is `null` but all specialist `findings` and `errors` are preserved in the response.
- The workflow status reflects partial failures:
  - `completed` — all agents succeeded
  - `completed_with_errors` — some agents failed but a plan was produced
  - `failed` — no review plan could be produced

## Next Phases
- Phase 4, Segment 2: Docker isolation and sandboxing for test execution.
- Phase 4, Segment 3: Verification agent to analyze test results.

## Phase 4 — Segment 1: Test Discovery and Deterministic Runtime Verification

Segment 1 introduces deterministic test discovery and execution directly on the local environment, serving as the foundation for runtime verification of code reviews. 

*Note: Docker isolation and sandboxing will be introduced in Phase 4 Segment 2.*

### Architectural Principle

Tests are runtime evidence. The LLM must **NOT** decide whether a test passed. The operating system/test runner determines exit codes, pass/fail status, and output. The system converts these results into structured data.

```
Repository
    ↓
Test Discovery
    ↓
Test Executor
    ↓
TestExecutionResult
```

### Features

- **Supported Framework**: `pytest`. The system is designed to be extensible to other frameworks in the future.
- **Discovery Strategy**: Automatically detects test files (`test_*.py`, `*_test.py`) and directories (`tests/`) without recursively scanning ignored directories like `.git`, `.venv`, or `node_modules`.
- **Execution Strategy**: Executes the full test suite or a targeted test path via a secure subprocess (`sys.executable -m pytest`). The working directory is strictly set to the repository root to ensure correct paths, imports, and config resolution.
- **Timeout Behavior**: Configurable execution timeout. If exceeded, the process is terminated and partial output is captured.
- **Output Limits**: Configurable character limits for `stdout` and `stderr` to prevent memory exhaustion, with clear truncation indicators.
- **Security & Validation**: Strict path validation prevents path traversal outside the repository boundary. Test paths are explicitly validated before execution.
- **Error Handling**: Uses structured errors (e.g., `TEST_TARGET_INVALID`, `TEST_EXECUTION_FAILED`) rather than raw stack traces.

### API Endpoints

#### POST `/api/tests/discover`
Discovers available tests in a target repository.

**Request:**
```json
{
  "repository_path": "C:\\Projects\\repo"
}
```

**Response:**
```json
{
  "framework": "pytest",
  "test_count": 1,
  "tests": [
    {
      "path": "tests/test_example.py",
      "framework": "pytest",
      "kind": "test_file"
    }
  ]
}
```

#### POST `/api/tests/run`
Executes tests in a target repository and parses the results deterministically. Supports `local` or `docker` execution mode.

**Request:**
```json
{
  "repository_path": "C:\\Projects\\repo",
  "test_path": null,
  "execution_mode": "docker"
}
```

**Response:**
```json
{
  "framework": "pytest",
  "execution_mode": "docker",
  "sandboxed": true,
  "status": "failed",
  "exit_code": 1,
  "duration_seconds": 1.82,
  "stdout": "============================= test session starts ...",
  "stderr": "",
  "tests_run": 2,
  "tests_passed": 1,
  "tests_failed": 1,
  "tests_skipped": 0,
  "tests_errors": 0,
  "output_truncated": false
}
```

## Phase 4 — Segment 2: Docker Sandboxed Execution

Executing unreviewed code directly on the host is highly unsafe. Phase 4 Segment 2 introduces a defense-in-depth approach by wrapping test execution inside ephemeral Docker sandboxes.

### Local vs. Docker Executor

- **Local Executor (`execution_mode="local"`)**: Runs tests securely bounded to the repo directory, but within the host environment. Useful for controlled internal testing.
- **Docker Sandbox (`execution_mode="docker"`)**: Runs the target repository's tests inside an isolated Docker container to protect the host machine from untrusted code.

### Security Controls

Docker sandboxing provides a strong layer of defense-in-depth against malicious repositories. The following restrictions are explicitly applied to every container test run:

- **Network Isolation**: `--network none` entirely disables network connectivity, preventing unauthorized data exfiltration or external dependencies being silently downloaded.
- **Read-Only Filesystem**: `--read-only` enforces a read-only root filesystem. The repository source itself is mounted read-only (`:ro`). Writable space is strictly confined to an ephemeral memory `tmpfs`.
- **Capabilities Dropped**: `--cap-drop ALL` removes default container privileges.
- **No New Privileges**: `--security-opt no-new-privileges=true` prevents internal privilege escalation.
- **Non-Root Execution**: Container explicitly executes with `-u 1000:1000`.
- **Resource Limits**: CPU (`--cpus`), memory (`--memory`), and process limits (`--pids-limit`) are enforced to avoid resource exhaustion and fork bombs.
- **Timeout**: The host enforcing a strict timeout kills the container if execution exceeds limits.
- **Ephemeral Cleanup**: `--rm` is used to automatically destroy containers and artifacts post-execution.

*Note: Docker provides defense-in-depth, but should not be treated as an absolute security boundary against advanced hypervisor escapes. The Docker sandbox must be configured securely on a trusted system.*

### Image Trust and Dependency Strategy

The system relies solely on **Trusted Images** supplied by application configuration (`DOCKER_IMAGE`).

- **No Target Dockerfiles**: The system **will not** build or execute Dockerfiles found inside the untrusted target repository. Doing so could lead to arbitrary command execution during image build.
- **No Dynamic Dependencies**: The system **will not** run `pip install -r requirements.txt` inside the container for the target repository. This prevents malicious packages from executing installation hooks (`setup.py`) inside the sandbox.
- **Preconfigured Environment**: The trusted image must come pre-installed with `pytest` and any dependencies the application officially supports testing. Tests for repositories with unfulfilled dependencies will simply fail execution.

### Docker Setup Documentation

To run the sandbox locally:
1. **Install Docker**: Install Docker Desktop (Windows/Mac) or Docker Engine (Linux).
2. **Create the Trusted Sandbox Image**: Do not use the base python image directly, as it lacks `pytest`. Build the official application sandbox image:
   ```sh
   docker build -t agentic-code-review-sandbox:latest -f docker/sandbox/Dockerfile .
   ```
3. **Verify the Image**: Ensure the image built correctly and `pytest` exists inside it:
   ```sh
   docker run --rm agentic-code-review-sandbox:latest python -m pytest --version
   ```
4. **Configure Image**: The `DOCKER_IMAGE` environment variable defaults to `agentic-code-review-sandbox:latest`. Set it in your `.env` if you use a different trusted image name.
5. **Run docker-mode tests**: Send a request to `POST /api/tests/run` with `"execution_mode": "docker"`.

*What happens if Docker is unavailable?* The API will immediately reject requests explicitly requesting `docker` execution mode. Fall back to `execution_mode="local"` if you are running in an environment without Docker support.

## Phase 4 � Segment 3: Runtime Verification Agent

The **Verification Agent** connects static code analysis to deterministic runtime evidence, validating AI-generated findings against actual test behavior. 

### Architecture

1. **Static Finding**: Security and Quality agents produce potential findings.
2. **Runtime Test Evidence**: The 	est_execution node runs the repository's test suite deterministically (via Docker if enabled).
3. **Verification Agent**: Identifies if the runtime evidence proves, contradicts, or is inconclusive about the finding.
4. **Output**: The Verification Agent assigns one of four statuses: erified, contradicted, inconclusive, or 
ot_tested.

### How Evidence Matches

Evidence matching relies heavily on **deterministic** signals rather than LLM guesswork:
- Finding file paths mapped to test file paths.
- Test names mentioned in the finding description.
- Exception types matching those found in the pytest output.

If relevant failure traces are discovered, the Verification Agent uses an LLM to interpret the semantics and make a final determination.

### Why Pass/Fail semantics matter
- **Tests passed** does **NOT** mean all findings are false (e.g., performance issues and security vulnerabilities often exist without test failures). Such results are marked inconclusive.
- **Test failed** does **NOT** automatically mean the finding is proven. The failure must directly support the claim (e.g. 	est_authentication fails exactly due to the KeyError mentioned in the finding) to be marked erified.

### LangGraph Workflow Topology
START -> planner -> context_agent -> (security_agent + quality_agent) -> test_execution -> verification_agent -> synthesizer -> END


 # #   P h a s e   4      S e g m e n t   4 :   R u n t i m e - A w a r e   F i n a l   S y n t h e s i s 
 
 T h e   * * S y n t h e s i z e r   A g e n t * *   a g g r e g a t e s   s t a t i c   f i n d i n g s   f r o m   t h e   s p e c i a l i s t   a g e n t s   a l o n g   w i t h   r u n t i m e   e v i d e n c e   t o   p r o d u c e   t h e   * * R u n t i m e - A w a r e   F i n a l   R e v i e w * * . 
 
 # # #   A r c h i t e c t u r e 
 S t a t i c   F i n d i n g s   
               +   
 R u n t i m e   T e s t   R e s u l t s   
               +   
 V e r i f i c a t i o n   R e s u l t s   
               �!
 F i n a l   S y n t h e s i z e r   
               �!
 R u n t i m e - A w a r e   F i n a l   R e v i e w 
 
 # # #   V e r i f i c a t i o n   S t a t u s   T y p e s 
 -   * * v e r i f i e d * * :   T h e   t e s t   f a i l u r e   e x a c t l y   m a t c h e s   a n d   p r o v e s   t h e   f i n d i n g . 
 -   * * c o n t r a d i c t e d * * :   T h e   c o d e   r a n   s u c c e s s f u l l y ,   d i r e c t l y   d i s p r o v i n g   a   c l a i m e d   c r a s h / e r r o r . 
 -   * * i n c o n c l u s i v e * * :   T e s t s   p a s s e d ,   b u t   c o u l d   n o t   d e f i n i t e l y   d i s p r o v e   t h e   f i n d i n g   ( e . g .   s e c u r i t y   v u l n e r a b i l i t i e s   w i t h o u t   e x p l i c i t   r e g r e s s i o n   t e s t s ) . 
 -   * * n o t _ t e s t e d * * :   N o   r e l e v a n t   t e s t s   w e r e   f o u n d   f o r   t h i s   i s s u e . 
 
 # # #   A P I   R e s p o n s e   F o r m a t 
 
 \ \ \ j s o n 
 { 
     \  
 s t a t u s \ :   \ c o m p l e t e d \ , 
     \ r e v i e w _ p l a n \ :   { . . . } , 
     \ f i n d i n g s \ :   [ . . . ] , 
     \ r u n t i m e _ t e s t _ r e s u l t \ :   { 
         \ s t a t u s \ :   \ f a i l e d \ , 
         \ t e s t s _ r u n \ :   1 0 , 
         \ t e s t s _ p a s s e d \ :   9 , 
         \ t e s t s _ f a i l e d \ :   1 , 
         \ e x e c u t i o n _ m o d e \ :   \ d o c k e r \ 
     } , 
     \ v e r i f i c a t i o n _ r e s u l t s \ :   [ 
         { 
             \ f i n d i n g _ i d \ :   \ s e c - 0 0 1 \ , 
             \ v e r i f i c a t i o n _ s t a t u s \ :   \ v e r i f i e d \ , 
             \ s u p p o r t i n g _ t e s t s \ :   [ \ t e s t s / t e s t _ a u t h . p y : : t e s t _ l o g i n \ ] , 
             \ e x p l a n a t i o n \ :   \ T e s t  
 f a i l e d  
 w i t h  
 t h e  
 e x a c t  
 e x c e p t i o n  
 r e p o r t e d . \ 
         } 
     ] , 
     \ f i n a l _ r e v i e w \ :   { 
         \ s u m m a r y \ :   \ 1  
 c r i t i c a l  
 i s s u e  
 v e r i f i e d  
 b y  
 t e s t s . \ , 
         \ o v e r a l l _ r i s k \ :   \ c r i t i c a l \ , 
         \ f i n d i n g s \ :   [ . . . ] , 
         \ r u n t i m e _ s u m m a r y \ :   { 
             \ s t a t u s \ :   \ f a i l e d \ , 
             \ t e s t s _ r u n \ :   1 0 
         } , 
         \ v e r i f i c a t i o n _ s u m m a r y \ :   { 
             \ v e r i f i e d \ :   1 , 
             \ c o n t r a d i c t e d \ :   0 , 
             \ i n c o n c l u s i v e \ :   0 , 
             \ n o t _ t e s t e d \ :   0 
         } 
     } , 
     \ e r r o r s \ :   [ ] 
 } 
 \ \ \ 
  
 