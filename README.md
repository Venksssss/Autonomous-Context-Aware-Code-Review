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

## Next Phases
- Phase 3, Segment 4: Synthesizer agent, final review report, memory, and Docker sandbox.
- Phase 4: GitHub PR automation and user-facing endpoints.
