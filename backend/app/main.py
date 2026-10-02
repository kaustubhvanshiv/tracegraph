"""TraceGraph FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import register_error_handlers
from app.api.auth import router as auth_router
from app.api.events import router as events_router
from app.api.investigations import router as investigations_router
from app.api.notes import router as notes_router
from app.api.timeline import router as timeline_router

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

# Register all parser adapters into the default registry on startup.
# This ensures every source_type is available for the ingestion pipeline
# before the first request arrives.
from app.adapters import register_default_adapters  # noqa: E402
register_default_adapters()

# Register API routers
app.include_router(auth_router)
app.include_router(investigations_router)
app.include_router(notes_router)
app.include_router(events_router)
app.include_router(timeline_router)


@app.get("/health")
async def health_check():
    """Liveness probe — returns ok when the process is running."""
    return {"status": "ok"}
