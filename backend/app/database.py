"""Database configuration, engine setup, and session management for FestivaFlow.

Provides SQLite connection pooling, foreign key constraint enforcement,
and context-managed database session generators.
"""

from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# Environment variable configuration with safe fallback for local/test/Vercel environments
_default_db_path = (
    "/tmp/festivaflow.db"
    if (os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
    else "./festivaflow.db"
)
DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{_default_db_path}")

# SQLite connection arguments: disabling thread check for multi-threaded ASGI servers
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Engine configuration with explicit connection pooling and timeout handling
engine: Engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """Enforce SQLite foreign key constraints upon establishing a new connection.

    Args:
        dbapi_connection: Raw database-level connection instance.
        connection_record: Connection record tracking object.
    """
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# Session factory for synchronous SQLAlchemy operations
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

# Declarative base class for all relational models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional database session for dependency injection.

    Yields:
        Session: Active SQLAlchemy session instance.

    Ensures:
        Session is closed deterministically after request lifecycle completion.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
