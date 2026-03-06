"""Database connection — SQLAlchemy async (patient service)."""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from ryx_shared.config import RyxConfig

config = RyxConfig()

engine = create_async_engine(
    config.database_url,
    pool_size=config.database_pool_size,
    max_overflow=config.database_max_overflow,
    echo=not config.is_production,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
