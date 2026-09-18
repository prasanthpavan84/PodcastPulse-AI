"""Pytest configuration and shared test fixtures."""

from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.main import app
from app.core.config import settings
from app.database.models import Base

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
    transaction.rollback()
    connection.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """FastAPI TestClient instance."""
    with TestClient(app) as test_client:
        yield test_client
