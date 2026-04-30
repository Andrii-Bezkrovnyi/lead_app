import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from testcontainers.postgres import PostgresContainer

from core.models.base import Base


@pytest.fixture(scope="session")
def postgres_container():
    """
    Starts a Postgres container for the duration of the test session
    and provides the connection URL.
    """
    with PostgresContainer("postgres:16") as postgres:
        db_url = postgres.get_connection_url().replace("psycopg2", "asyncpg")
        yield db_url


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine(postgres_container):
    """Creates an async SQLAlchemy engine connected to the test Postgres container."""
    engine = create_async_engine(
        postgres_container,
        poolclass=NullPool,
        echo=False
    )

    async with engine.begin() as conn:
        """Creates the database schema before any tests run."""
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def session(engine):
    """For gets a connection from the pool and starts a transaction for each test."""
    # Get a connection from the pool
    async with engine.connect() as conn:
        # Begin a transaction on this connection
        transaction = await conn.begin()

        # Bind session to this connection and transaction
        async_session = async_sessionmaker(
            bind=conn,
            expire_on_commit=False,
            class_=AsyncSession,
            join_transaction_mode="create_savepoint"
        )

        async with async_session() as session_obj:
            yield session_obj

        await transaction.rollback()
