"""TraceGraph FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import register_error_handlers

app = FastAPI(
    title="TraceGraph API",
    description=(
        "Security investigation platform — graph, timeline, and AI-assisted analysis"
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register global exception handlers after middleware so all requests are covered.
register_error_handlers(app)


@app.get("/health")
async def health_check():
    """Liveness probe — returns ok when the process is running."""
    return {"status": "ok"}
