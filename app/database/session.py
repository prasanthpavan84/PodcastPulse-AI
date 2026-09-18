"""Database engine and session management for MySQL 8."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.errors import DatabaseError

# Production/development MySQL 8 engine
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    session: Session = SessionLocal()
    try:
        yield session
    except Exception as exc:
        session.rollback()
        raise DatabaseError(f"Database transaction failed: {exc}") from exc
    finally:
        session.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager for standalone database operations with transactional commit."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        raise DatabaseError(f"Database error during unit of work: {exc}") from exc
    finally:
        session.close()


def check_database_connection() -> bool:
    """Check connectivity to MySQL database."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True
    except Exception:
        return False
