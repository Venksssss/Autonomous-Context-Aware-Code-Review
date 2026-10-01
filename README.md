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

Those capabilities are Segment 3.

## Next Phases
- **Segment 3**: Cross-file symbol resolution and intra-repository call graph construction.
- RAG and Vector database integration.
- LLM-based autonomous reviews.
- Testing sandboxes and MCP integration.
