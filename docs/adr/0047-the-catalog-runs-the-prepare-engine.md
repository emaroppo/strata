# 47. The catalog runs the prepare engine, and prepare never imports the catalog

**Status:** proposed; amends record 0040

## The decision

`strata-catalog` depends on `strata-prepare`. The catalog runs ingest
and prepare (records 0045, 0046). It resolves a run's inputs from its
raw rows, hands the files to the stage engine, and writes the samples,
origin rows and run it gets back. `strata-prepare` never imports the
catalog. Every command that reads or writes a catalog is
`strata-catalog`'s.

## What this amends, and why

**Record 0040 said that "neither of the last two imports the other".
That becomes "prepare never imports the catalog".**

Record 0040 named one cost, and it runs one way only: a preparer
"should not need a database driver to find out" what it produces. When
the types lived in the catalog, every plugin depended on SQLAlchemy and
alembic. That cost is still kept away. The stage engine, the spec model,
the stage contract and its conformance suite need only the contracts and
`strata-common`. So a plugin such as `prepare-email` still installs
without a database.

The other direction costs nothing. `strata-prepare` brings only what the
catalog already depends on. What changed is where ingest and prepare
live. They used to be a project's, run by the labeller from
`project.toml`. Record 0045 makes them the catalog's own operations. So
the catalog is what has to run the engine.

## Why not another home

- **The labeller.** That is where a prepared corpus is ingested today,
  but it is built around `project.toml`, and these operations
  deliberately belong to no project.
- **A new orchestration package.** It would exist only to avoid an
  import that costs nothing.

## Consequences

- **Commands that read or write a catalog:**
  - `strata-catalog ingest` for raw files, with `--prepare <spec>` for
    the combined pass;
  - `strata-catalog prepare <spec>`;
  - `strata-catalog lineage <checksum>`;
  - `strata-catalog runs`;
  - `strata-catalog verify --run <id>`.
- **`strata-prepare` keeps the commands that read no catalog:**
  `validate <spec>` and `stages`.
- **`strata-labeller ingest` of a prepared corpus** stays for projects
  that have not moved, until the folder preparers are ported.
- **A test fails if `strata-prepare` imports `strata.catalog`,** as
  post-process fails one if it imports the feature store.
