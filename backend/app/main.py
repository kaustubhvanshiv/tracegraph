"""TraceGraph FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import register_error_handlers
from app.api.investigations import router as investigations_router
from app.api.notes import router as notes_router

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

# Register API routers
app.include_router(investigations_router)
app.include_router(notes_router)


@app.get("/health")
async def health_check():
    """Liveness probe — returns ok when the process is running."""
    return {"status": "ok"}
