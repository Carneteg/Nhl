"""Database configuration and request-scoped sessions."""
import os
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nhl.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    """Base class shared by every persisted model."""

def get_db() -> Generator[Session, None, None]:
    """Yield a transaction and always release its connection."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

