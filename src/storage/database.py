from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.config.settings import settings
from src.storage.models import Base

# Setup the async engine
engine = create_async_engine(settings.database_url, echo=False)

# Create an async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db():
    """Dependency for providing a database session."""
    async with AsyncSessionLocal() as session:
        yield session

async def init_db():
    """Initialize the database by creating all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
