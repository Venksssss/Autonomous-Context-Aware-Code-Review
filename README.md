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

## Known Limitations
- Currently, it only inspects a local filesystem path and extracts Git diffs deterministically.
- Does not decode binary file diffs as text.

## Future Phases
- RAG and Vector database integration.
- LLM-based autonomous reviews.
- Testing sandboxes and MCP integration.
