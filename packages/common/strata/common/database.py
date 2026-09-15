"""Opening an engine the way every strata database wants it opened.

SQLite gets WAL and ``synchronous=NORMAL`` for the bulk write; on any
other dialect this is ``create_engine`` and nothing more. See
``docs/adr/0021``.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine


def engine(url: str) -> Engine:
    """An engine on ``url``, with SQLite tuned for writes and concurrent reads."""
    made = create_engine(url)
    if made.dialect.name == "sqlite":

        @event.listens_for(made, "connect")
        def _pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return made


__all__ = ["engine"]
