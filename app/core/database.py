from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from typing import AsyncGenerator

# --- Async engine: used by FastAPI request handlers ---
engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# --- Sync engine: used by Celery workers ---
# Mixing an asyncpg-based async engine with asyncio.run() inside a Celery
# task (especially under the default prefork pool) is a known source of
# "connection created in a different event loop" bugs after fork. The task
# body has no real concurrent I/O to gain from async anyway, so a plain
# sync session is simpler and avoids the risk entirely.
def _to_sync_url(url: str) -> str:
    return url.replace("+asyncpg", "")

sync_engine = create_engine(_to_sync_url(settings.database_url), echo=False)
SyncSessionLocal = sessionmaker(bind=sync_engine, expire_on_commit=False)