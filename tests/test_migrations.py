"""Alembic migrations: head upgrade produces the full schema on a fresh DB."""

from __future__ import annotations


def test_alembic_upgrade_head_creates_schema(tmp_path, monkeypatch):
    import sqlite3
    from pathlib import Path

    from alembic.config import Config

    from alembic import command

    root = Path(__file__).resolve().parents[1]
    db_path = tmp_path / "migrated.db"
    # env.py resolves the URL from OWNERAI_DATABASE_URL (same as the app)
    monkeypatch.setenv("OWNERAI_DATABASE_URL",
                       f"sqlite+aiosqlite:///{db_path.as_posix()}")

    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "alembic"))

    command.upgrade(cfg, "head")

    con = sqlite3.connect(str(db_path))
    tables = {row[0] for row in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "sessions", "audit_log",
            "rate_counters", "login_failures", "alembic_version"} <= tables

    # downgrade then upgrade again must also work
    command.downgrade(cfg, "base")
    tables_after_down = {row[0] for row in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "users" not in tables_after_down

    command.upgrade(cfg, "head")
    tables_after_up = {row[0] for row in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "users" in tables_after_up
    con.close()
