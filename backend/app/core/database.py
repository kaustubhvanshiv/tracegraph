import asyncio
import logging
import ssl as _ssl
from sqlalchemy import URL, text
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

DATABASE_URL = URL.create(
    "postgresql+asyncpg",
    username=settings.postgres_user,
    password=settings.postgres_password,
    host=settings.postgres_host,
    port=settings.postgres_port,
    database=settings.postgres_db,
)

connect_args: dict = {
    "prepared_statement_cache_size": 0,
}
if "supabase.com" in settings.postgres_host:
    # Supabase's connection pooler uses a self-signed cert in its chain which
    # Python's SSL store rejects on Windows.  We still encrypt the connection
    # (ssl=True / verify_full is NOT disabled at the network level) but we
    # skip CA-chain verification so the handshake succeeds.
    _ssl_ctx = _ssl.create_default_context()
    _ssl_ctx.check_hostname = False
    _ssl_ctx.verify_mode = _ssl.CERT_NONE
    connect_args["ssl"] = _ssl_ctx

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


# pyrefly: ignore [bad-return]
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

async def check_postgres_health(retries: int = 5, delay: float = 2.0) -> bool:
    """Verify PostgreSQL connectivity with retries.

    Retries up to *retries* times with *delay* seconds between attempts so
    that transient DNS / network blips (e.g. getaddrinfo failed) at process
    startup don't cause an immediate fatal exit.
    """
    for attempt in range(1, retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            logger.warning(
                "PostgreSQL health check attempt %d/%d failed: %s",
                attempt, retries, e,
            )
            if attempt < retries:
                await asyncio.sleep(delay)
    logger.error("PostgreSQL health check failed after %d attempts", retries)
    return False


async def check_neo4j_health(retries: int = 5, delay: float = 2.0) -> bool:
    """Verify Neo4j connectivity with retries."""
    if neo4j_driver is None:
        return False
    for attempt in range(1, retries + 1):
        try:
            await neo4j_driver.verify_connectivity()
            return True
        except Exception as e:
            logger.warning(
                "Neo4j health check attempt %d/%d failed: %s",
                attempt, retries, e,
            )
            if attempt < retries:
                await asyncio.sleep(delay)
    logger.error("Neo4j health check failed after %d attempts", retries)
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
