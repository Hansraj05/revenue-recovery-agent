from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


def _to_async_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    if url.startswith("postgresql://"):
        url = url.replace(
            "postgresql://", "postgresql+asyncpg://", 1
        )

    return url


def _to_sync_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    url = url.replace("postgresql+asyncpg://", "postgresql://", 1)

    if url.startswith("postgresql://"):
        url = url.replace(
            "postgresql://", "postgresql+psycopg2://", 1
        )

    return url

# --- Async engine: used by FastAPI request handlers ---
engine = create_async_engine(_to_async_url(settings.database_url), echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


# --- Sync engine: used by Celery workers ---
sync_engine = create_engine(_to_sync_url(settings.database_url), echo=False, pool_pre_ping=True)
SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)