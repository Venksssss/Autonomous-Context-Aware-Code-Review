from fastapi import FastAPI
from app.api.routes import repositories, code, repository

app = FastAPI(
    title="Autonomous Context-Aware Code Review API",
    description="Phase 1 - Segment 1: Project Foundation + Git Repository Ingestion",
    version="1.0.0"
)

app.include_router(repositories.router, prefix="/api/repositories", tags=["Repositories"])
app.include_router(repository.router, prefix="/api/repository", tags=["Repository Graph"])
app.include_router(code.router, prefix="/api/code", tags=["Code Parsing"])

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
