from fastapi import FastAPI
from app.api.routes import repositories, code, repository, ai, tests

app = FastAPI(
    title="Autonomous Context-Aware Code Review API",
    description="Phase 1 - Segment 1: Project Foundation + Git Repository Ingestion",
    version="1.0.0"
)

app.include_router(repositories.router, prefix="/api/repositories", tags=["Repositories"])
app.include_router(repository.router, prefix="/api/repository", tags=["Repository Graph"])
app.include_router(code.router, prefix="/api/code", tags=["Code Parsing"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI Planning"])
app.include_router(tests.router, prefix="/api/tests", tags=["Test Execution"])

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
