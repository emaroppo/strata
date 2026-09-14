# 18. Opening never creates, a new store is stamped at head, and a database is refused rather than upgraded in passing

**Status:** accepted

## The decision

Opening a catalog or a run store verifies and writes nothing. `Catalog.connect`
checks the recorded migration revision against the code's head and touches
nothing else; an index with no catalog in it is `CatalogMissing`, and one
behind the code is refused with the command that brings it forward. Creating
is a separate call, `Catalog.create`, which builds the schema, stamps the head
revision and mints the identity, and only for a database it found empty; on an
existing one it opens. `open_catalog` routes by the caller's word, and only the
commands that put data in pass `create`. Migrations read the same `[catalog]`
tables as every other reader, with no `alembic.ini`; each package ships its own
chain and the command that runs it.

## Why opening must not create

A command that only consults a catalog must not be able to leave an empty one
behind, where it would hide the catalog configured somewhere else and answer
every question with nothing. And a plain open must never issue DDL: with
`create_all` on every open, a table added by a migration was created out of
band before the migration guard ran, and the next `upgrade` failed on a table
that already existed. Opening also used to mint an identity, so whichever
client looked first at a partially restored index gave it a fresh one, which is
the failure record 0008 exists to prevent.

## Why a new store is stamped rather than migrated

`create_all` keeps a checkout runnable and the suite fast, and a database built
that way is at head by construction, so it is stamped at head. Without the
stamp the first `upgrade` would replay the baseline against tables that already
exist. Only a database this process found empty is stamped: one that already
held tables and carries no revision predates migrations and is at the baseline,
and stamping it at head would have it claim columns it does not have, leaving a
later `upgrade` with nothing to do.

## Why refused rather than upgraded in passing

A migration rewrites somebody's data. Doing that as a side effect of opening a
connection is not a decision the code should make on their behalf. And refused
rather than ignored, because the alternative is a missing column surfacing as a
query error far from the cause. The refusal names the command to run.

## Consequences

- A read-only database role can open a catalog.
- The head revision is read from disk once per process, since the modelling
  host opens a catalog per request.
- The run store follows the same shape: `RunStore.open` verifies and never
  creates, `RunStore.local` makes a store if there is none and opens it if
  there is, and the prediction cache opens the store rather than building
  tables of its own. `push` and `report` consult; a round, a merge's target
  and the modelling host write.
- Ingest passes `create` on every run and never mints a second identity,
  because `create` on an existing store is an open.
