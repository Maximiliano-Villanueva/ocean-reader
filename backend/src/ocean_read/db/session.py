import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from ocean_read.config import get_settings

_settings = get_settings()

_use_null_pool = (os.getenv("OCEAN_READ_TEST_NULL_POOL") or "").lower() in {"1", "true", "yes"}


def _async_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine = create_async_engine(
    _async_database_url(_settings.database_url),
    echo=False,
    pool_pre_ping=not _use_null_pool,
    **({"poolclass": NullPool} if _use_null_pool else {}),
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
