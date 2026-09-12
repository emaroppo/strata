"""Opening an engine the way every strata database wants it opened.

One schema, two dialects, is the rule in each package: SQLite for a
checkout with nothing installed, Postgres where several machines read one
index. The pragmas below are what make SQLite bearable for a bulk write —
a full fsync per commit is what makes an import crawl, and WAL lets a
reader run while a writer does. Neither has an equivalent worth setting on
Postgres, so on any other dialect this is ``create_engine`` and nothing more.

``synchronous=NORMAL`` under WAL can lose the last transactions on a power
cut and cannot corrupt the file. Right for an index rebuildable from its
blobs and a cache rebuildable from its checkpoints; for a run store it is
the trade taken knowingly, since a run's checkpoint outlives its row.
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
