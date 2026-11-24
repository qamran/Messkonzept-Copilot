"""Declarative base for all ORM models. Alembic reads `Base.metadata`."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for the SQLAlchemy models that later tickets add."""
