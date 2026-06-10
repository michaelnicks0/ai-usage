"""SQLite persistence for usage snapshots."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone


class SnapshotDB:
    """Manages the snapshots SQLite database."""

    def __init__(self, db_path: str | None = None) -> None:
        if db_path is None:
            hermes_dir = os.path.expanduser("~/.hermes")
            os.makedirs(hermes_dir, exist_ok=True)
            db_path = os.path.join(hermes_dir, "ai-usage.db")
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        """Lazy-initialize the connection (singleton per instance)."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp     TEXT    NOT NULL,
                    provider      TEXT    NOT NULL,
                    balance       REAL,
                    spend         REAL,
                    tokens_input  INTEGER DEFAULT 0,
                    tokens_cached INTEGER DEFAULT 0,
                    tokens_output INTEGER DEFAULT 0
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_provider_ts
                ON snapshots(provider, timestamp)
            """)
            self._conn.commit()
        return self._conn

    def save(self, provider: str, balance: float | None, spent: float | None,
             input_tokens: int = 0, cached_tokens: int = 0, output_tokens: int = 0) -> None:
        """Insert a snapshot row."""
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.conn.execute(
            "INSERT INTO snapshots (timestamp, provider, balance, spend, "
            "tokens_input, tokens_cached, tokens_output) "
            "VALUES (?,?,?,?,?,?,?)",
            (now, provider, balance, spent,
             input_tokens or 0, cached_tokens or 0, output_tokens or 0),
        )
        self.conn.commit()

    def query(
        self,
        provider: str | None = None,
        limit: int = 10,
        provider_count: int = 9,
    ) -> list[tuple]:
        """Return snapshot rows, newest first."""
        if provider:
            rows = self.conn.execute(
                "SELECT timestamp, provider, balance, spend, "
                "tokens_input, tokens_cached, tokens_output "
                "FROM snapshots WHERE provider=? "
                "ORDER BY timestamp DESC LIMIT ?",
                (provider, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT timestamp, provider, balance, spend, "
                "tokens_input, tokens_cached, tokens_output "
                "FROM snapshots "
                "ORDER BY timestamp DESC LIMIT ?",
                # Multiply by provider count so --history-limit means fetch groups.
                (limit * provider_count,),
            ).fetchall()
        return rows

    def close(self) -> None:
        """Close the connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
