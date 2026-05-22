from __future__ import annotations
"""
ClinNote AI — Cross-Database UUID TypeDecorator
================================================
Provides a UUID column type that:
  - Uses native PostgreSQL UUID on PostgreSQL (avoids VARCHAR cast errors)
  - Falls back to String(36) for SQLite (used in tests via aiosqlite)

Without this, asyncpg sends UUID values as $1::VARCHAR which PostgreSQL
rejects with: column "id" is of type uuid but expression is of type character varying
"""

import uuid

from sqlalchemy import String, types
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


class UUIDType(types.TypeDecorator):
    """
    Database-agnostic UUID column type.

    PostgreSQL: native UUID (no cast errors with asyncpg)
    SQLite:     VARCHAR(36) string representation
    """

    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
