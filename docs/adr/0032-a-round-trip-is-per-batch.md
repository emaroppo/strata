# 32. A round trip is per batch, never per sample, and a re-run carries on from the last

**Status:** accepted

## The decision

Work against a database or a service happens per batch. An ingest batch is one
transaction; features are read with one query per declaration; parameters are
chunked; a freeze writes one statement per chunk of members and a repack one
per shard; tasks are created in chunks. What a failed batch left behind stays,
and a re-run carries on from there rather than starting over.

## Why per batch

A commit per file is an fsync per file, which is what makes an import crawl. A
query per sample over a pool of tens of thousands is a pool that never
finishes. SQLite's parameter cap depends on the interpreter build, 250,000 on
one machine and 32,766 on another, and a corpus once failed to ingest on the
second; chunking is what makes the same code run on both.

## Why a re-run carries on

Chunks committed before a failure are real, and throwing them away to restart
cleanly would make a large import that fails near the end cost twice. So
ingest skips what the catalog already has, task creation skips tasks that
exist, and a chunk that came back without positional ids is skipped rather than
guessed, with `--rebuild-map` to recover the mapping by listing. Idempotence on
content (record 0001) is what makes carrying on safe.

## Consequences

- Progress is reported within the batch (record 0031), since a batch can be
  long.
- The repack keeps no progress file; the index is the record of what is done,
  so nothing can fall out of step with it.
