# 21. One schema, two dialects: the local catalog needs no infrastructure

**Status:** accepted

## The decision

Storage and index are separate axes. The index is SQLite or Postgres against
one schema; blobs are files in a directory or tar shards in a bucket. The local
pair, SQLite beside a blob directory, needs nothing installed, and it runs the
same schema and the same queries as the server configuration. Everything goes
through one `Catalog` object, so swapping one pair for the other is not noticed
by a caller.

## Why

A fresh clone has to run with nothing but Python, and a corpus of millions of
rows read from several machines is where SQLite stops being the right answer.
The two are one code path rather than two products, which is what keeps the
tests meaningful for the deployment and the deployment honest about the tests.
An empty index URL is SQLite under the catalog root; a Postgres URL, written
without its password, points several machines at one index.

## The portability rules that follow

- Core, not the ORM: rows are data, and behaviour lives in `labels`.
- A sample in several collections is selected with EXISTS rather than a join,
  because one dialect cannot DISTINCT over JSON and the other duplicates
  silently.
- Metadata is filtered in Python, since JSON access differs by dialect.
- A migration that rewrites stored values goes through the JSON column so the
  same code runs on both, and rebuilds a table rather than altering a primary
  key, which SQLite cannot do in place.
- SQLite is tuned for the bulk write: WAL so a reader runs while a writer does,
  and `synchronous=NORMAL`, which can lose the last transactions on a power cut
  and cannot corrupt the file. Right for an index rebuildable from its blobs
  and a cache rebuildable from its checkpoints; for a run store the trade is
  taken knowingly, since a checkpoint outlives its row. On any other dialect
  the engine factory is `create_engine` and nothing more.
