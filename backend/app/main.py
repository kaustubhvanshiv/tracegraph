"""TraceGraph FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.errors import register_error_handlers
from app.api.events import router as events_router
from app.api.graph import router as graph_router
from app.api.investigations import router as investigations_router
from app.api.notes import router as notes_router
from app.api.summary import router as summary_router
from app.api.timeline import router as timeline_router

from contextlib import asynccontextmanager
import sys
from app.core.database import init_neo4j, close_neo4j, engine, check_postgres_health, check_neo4j_health
from app.models.base import Base
from app.models.investigation import InvestigationModel
from app.models.security_event import SecurityEventModel
from app.models.note import InvestigationNoteModel
from app.models.event_entity_map import EventEntityMapModel

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Neo4j driver
    await init_neo4j()
    
    # Check health before proceeding
    if not await check_postgres_health():
        print("CRITICAL ERROR: Cannot establish connection to PostgreSQL database. Exiting.", file=sys.stderr)
        sys.exit(1)
        
    if not await check_neo4j_health():
        print("CRITICAL ERROR: Cannot establish connection to Neo4j database. Exiting.", file=sys.stderr)
        sys.exit(1)

    # Create PostgreSQL tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Cleanup
    await close_neo4j()

app = FastAPI(
    title="TraceGraph API",
    description=(
        "Security investigation platform — graph, timeline, and AI-assisted analysis"
    ),
    version="0.1.0",
    lifespan=lifespan,
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

from app.core.logging import setup_logging
setup_logging()

# Register all parser adapters into the default registry on startup.
# This ensures every source_type is available for the ingestion pipeline
# before the first request arrives.
from app.adapters import register_default_adapters  # noqa: E402
register_default_adapters()

# Register API routers
app.include_router(investigations_router)
app.include_router(notes_router)
app.include_router(events_router)
app.include_router(timeline_router)
app.include_router(graph_router)
app.include_router(summary_router)


@app.get("/health")
async def health_check():
    """Liveness probe — returns ok when the process is running."""
    return {"status": "ok"}
