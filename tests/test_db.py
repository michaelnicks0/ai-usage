"""Tests for SQLite database."""

from __future__ import annotations

from ai_usage.db import SnapshotDB


class TestSnapshotDB:
    def test_creates_tables(self, temp_db_path):
        db = SnapshotDB(temp_db_path)
        # Querying before any inserts should return empty
        rows = db.query()
        assert rows == []
        db.close()

    def test_save_and_query(self, temp_db_path):
        db = SnapshotDB(temp_db_path)
        db.save("deepseek", balance=10.50, spent=2.25,
                input_tokens=1000, cached_tokens=500, output_tokens=200)
        rows = db.query()
        assert len(rows) == 1
        ts, prov, bal, spd, inp, cached, outp = rows[0]
        assert prov == "deepseek"
        assert bal == 10.50
        assert spd == 2.25
        assert inp == 1000
        assert cached == 500
        assert outp == 200
        db.close()

    def test_filter_by_provider(self, temp_db_path):
        db = SnapshotDB(temp_db_path)
        db.save("deepseek", balance=10, spent=1)
        db.save("xai", balance=20, spent=2)
        db.save("deepseek", balance=9, spent=1.5)

        rows = db.query(provider="deepseek", limit=5)
        assert len(rows) == 2
        assert all(r[1] == "deepseek" for r in rows)

        rows = db.query(provider="xai", limit=5)
        assert len(rows) == 1
        assert rows[0][1] == "xai"
        db.close()

    def test_limit(self, temp_db_path):
        db = SnapshotDB(temp_db_path)
        for i in range(5):
            db.save("deepseek", balance=float(i), spent=0)
        rows = db.query(provider="deepseek", limit=2)
        assert len(rows) == 2
        db.close()

    def test_close_is_idempotent(self, temp_db_path):
        db = SnapshotDB(temp_db_path)
        db.close()
        db.close()  # should not raise
