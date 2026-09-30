import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PostgreSQL — async engine
# ---------------------------------------------------------------------------

DATABASE_URL = (
    f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
)

connect_args = {
    "prepared_statement_cache_size": 0,
}
if "supabase.com" in settings.postgres_host:
    connect_args["ssl"] = "require"

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.app_env == "development",
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session."""
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# Neo4j — async driver
# ---------------------------------------------------------------------------

neo4j_driver = None


async def init_neo4j() -> None:
    """Initialize the Neo4j async driver. Called during app startup."""
    from neo4j import AsyncGraphDatabase  # type: ignore[import-untyped]

    global neo4j_driver
    neo4j_driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


async def close_neo4j() -> None:
    """Close the Neo4j async driver. Called during app shutdown."""
    if neo4j_driver is not None:
        await neo4j_driver.close()


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------

async def check_postgres_health() -> bool:
    """Verify PostgreSQL connectivity."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("PostgreSQL health check failed: %s", e)
        return False


async def check_neo4j_health() -> bool:
    """Verify Neo4j connectivity."""
    if neo4j_driver is None:
        return False
    try:
        await neo4j_driver.verify_connectivity()
        return True
    except Exception as e:
        logger.error("Neo4j health check failed: %s", e)
        return False


async def check_db_health() -> dict[str, bool]:
    """Check connectivity to all databases."""
    return {
        "postgres": await check_postgres_health(),
        "neo4j": await check_neo4j_health(),
    }


# ---------------------------------------------------------------------------
# FastAPI dependency for Neo4j driver
# ---------------------------------------------------------------------------


async def get_neo4j_driver():
    """FastAPI dependency that yields the global Neo4j async driver.

    The driver is initialised during app startup via ``init_neo4j()``.
    Callers that need the driver inside a route handler should declare::

        driver = Depends(get_neo4j_driver)
    """
    return neo4j_driver

