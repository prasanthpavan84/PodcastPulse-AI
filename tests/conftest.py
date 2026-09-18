"""Pytest configuration and shared test fixtures."""

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.adapters.mocks import MockYouTubeDiscovery
from app.api.main import app
from app.core.config import settings
from app.database.models import Base
from app.database.session import get_db

# Dedicated MySQL 8 integration test engine
test_engine = create_engine(
    settings.test_database_url,
    echo=False,
    pool_pre_ping=True,
)

TestSessionLocal = sessionmaker(
    bind=test_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Create all schema tables in MySQL 8 test database (podcastpulse_test)."""
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def mysql_session() -> Generator[Session, None, None]:
    """Provide an isolated database session running against MySQL 8 test database."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI TestClient instance configured to use MySQL 8 test database."""

    def _test_get_db() -> Generator[Session, None, None]:
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _test_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def mock_youtube_adapter() -> MockYouTubeDiscovery:
    """Fixture providing a fresh MockYouTubeDiscovery instance."""
    return MockYouTubeDiscovery()
