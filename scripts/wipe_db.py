import asyncio
from app.core.database import engine
from app.models import Base

async def wipe():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables and schemas completely rebuilt!")

if __name__ == "__main__":
    asyncio.run(wipe())