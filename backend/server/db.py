from __future__ import annotations

import asyncio
from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from server.config import settings
from server.models.base import Base

_engine: AsyncEngine | None = None
_session_factory: sessionmaker[AsyncSession] | None = None
_schema_initialized = False
_schema_lock = asyncio.Lock()


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        # Support both async and sync-style SQLite URLs in .env.
        # If a plain `sqlite:///...` URL is provided, convert it to
        # `sqlite+aiosqlite:///...` so `create_async_engine` is given
        # an async-capable driver. Keep the original `settings.DATABASE_URL`
        # value unchanged for other uses.
        raw_url = settings.DATABASE_URL
        if raw_url.startswith("sqlite://") and not raw_url.startswith("sqlite+"):
            engine_url = raw_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        else:
            engine_url = raw_url

        connect_args = {"check_same_thread": False} if "sqlite" in raw_url else {}
        pool_kwargs = {}
        if raw_url.endswith(":memory:") or raw_url.endswith(":memory:"):
            pool_kwargs["poolclass"] = StaticPool
        _engine = create_async_engine(
            engine_url,
            future=True,
            echo=False,
            connect_args=connect_args,
            **pool_kwargs,
        )
        if "sqlite" in raw_url:
            @event.listens_for(_engine.sync_engine, "connect")
            def _set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.execute("PRAGMA foreign_keys=ON")
                cursor.close()
    return _engine


def get_session_factory() -> sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


def make_session() -> AsyncSession:
    return get_session_factory()()


async def init_db() -> None:
    await ensure_schema_initialized()


def _run_migrations(conn) -> None:
    """Add columns that create_all cannot add to existing tables."""
    import sqlalchemy as sa

    inspector = sa.inspect(conn)
    if inspector.has_table("users"):
        columns = {c["name"] for c in inspector.get_columns("users")}
        if "display_name" not in columns:
            conn.execute(sa.text("ALTER TABLE users ADD COLUMN display_name VARCHAR(128)"))
    if inspector.has_table("messages"):
        columns = {c["name"] for c in inspector.get_columns("messages")}
        if "session_id" not in columns:
            conn.execute(sa.text("ALTER TABLE messages ADD COLUMN session_id VARCHAR(64) REFERENCES interview_sessions(id)"))

    for stale in ("system_prompts", "documents"):
        if inspector.has_table(stale):
            conn.execute(sa.text(f"DROP TABLE {stale}"))

    if inspector.has_table("assessment_criteria"):
        count = conn.execute(sa.text("SELECT COUNT(*) FROM assessment_criteria")).scalar()
        if count == 0:
            _seed_default_criteria(conn)


def _seed_default_criteria(conn) -> None:
    """Insert default assessment criteria when the table is empty."""
    import sqlalchemy as sa
    import uuid as _uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    criteria = [
        ("Решения", "Способность предлагать решения и работать с возражениями", 10.0, 1.0, 1),
        ("Эмпатия", "Эмоциональный интеллект и установление контакта", 10.0, 1.0, 2),
        ("Информация", "Ясность, полнота и точность предоставленной информации", 10.0, 1.0, 3),
        ("Коммуникация", "Навыки речи, профессионализм, качество языка", 10.0, 1.0, 4),
        ("Релевантность опыта", "Насколько предыдущий опыт соответствует позиции", 10.0, 0.8, 5),
    ]
    for name, desc, max_score, weight, order in criteria:
        conn.execute(
            sa.text(
                "INSERT INTO assessment_criteria "
                "(id, name, description, max_score, weight, is_active, display_order, created_at) "
                "VALUES (:id, :name, :desc, :max, :w, 1, :ord, :ts)"
            ),
            {"id": str(_uuid.uuid4()), "name": name, "desc": desc,
             "max": max_score, "w": weight, "ord": order, "ts": now},
        )


async def ensure_schema_initialized() -> None:
    global _schema_initialized
    if _schema_initialized:
        return
    async with _schema_lock:
        if _schema_initialized:
            return
        engine = _get_engine()

        raw_url = settings.DATABASE_URL
        if "sqlite" in raw_url:
            import os
            db_path = raw_url.split("///", 1)[-1] if "///" in raw_url else ""
            if db_path:
                os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.run_sync(_run_migrations)
        _schema_initialized = True


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    await ensure_schema_initialized()
    factory = get_session_factory()
    async with factory() as session:
        yield session
