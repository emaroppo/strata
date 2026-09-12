"""A SQLite engine comes tuned; the tuning is per connection, not per call."""

from sqlalchemy import text

from strata.common.database import engine


def test_sqlite_runs_in_wal_with_normal_sync(tmp_path):
    made = engine(f"sqlite:///{tmp_path / 'thing.db'}")
    with made.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA synchronous")).scalar() == 1


def test_every_connection_gets_the_pragmas(tmp_path):
    made = engine(f"sqlite:///{tmp_path / 'thing.db'}")
    for _ in range(2):
        with made.connect() as conn:
            assert conn.execute(text("PRAGMA synchronous")).scalar() == 1
