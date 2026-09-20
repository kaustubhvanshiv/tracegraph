"""Database connection management for PostgreSQL (SQLAlchemy async) and Neo4j."""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# ---------------------------------------------------------------------------
# PostgreSQL — async engine (Supabase connection pooler)
#
# Supabase uses pgBouncer in transaction-pooling mode, which does not support
# prepared statements. Two tweaks are required:
#   1. Disable prepared statement caching via the connect_args option.
#   2. Enable SSL (Supabase requires it on the pooler endpoint).
# ---------------------------------------------------------------------------

DATABASE_URL = (
    f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.app_env == "development",
    # pgBouncer (transaction mode) does not support server-side prepared statements
    connect_args={
        "prepared_statement_cache_size": 0,
        "ssl": "require",
    },
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

# Initialized lazily on app startup via init_neo4j().
neo4j_driver = None


async def init_neo4j() -> None:
    """Initialize the Neo4j async driver.  Called during app startup."""
    from neo4j import AsyncGraphDatabase  # type: ignore[import-untyped]

    global neo4j_driver
    neo4j_driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
    )


async def close_neo4j() -> None:
    """Close the Neo4j async driver.  Called during app shutdown."""
    if neo4j_driver is not None:
        await neo4j_driver.close()
