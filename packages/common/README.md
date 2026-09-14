# strata-common

What two strata packages need and neither owns. Deliberately thin: the
base install carries no dependency at all, and each module that needs one
sits behind an extra, so a plugin resolver never pulls in a database
driver.

```bash
uv add strata-common                  # canonical form, plugins, stages
uv add "strata-common[migrations]"    # sqlalchemy, alembic
uv add "strata-common[service]"       # uvicorn
```

## What it holds

| module | what it is | extra |
|---|---|---|
| `canonical` | one canonical JSON form for anything that gets hashed: `canonical_json`, `canonical_bytes`, `content_hash`, `short_hash`. One implementation, imported by `strata-post-process` and `strata-feature-store` too; `contract` ships the payload every consumer pins the digest of | none |
| `plugins` | resolving a name through an entry-point group: `available`, `find`, `load`. Refuses an ambiguity rather than picking a winner, and reserves built-in names | none |
| `stages` | `Stage(name, version, consumes, produces, run)`: the contract a pipeline stage meets, so an experiment file can sequence stages from several packages | none |
| `database` | `engine(url)`: the one engine factory, with the SQLite pragmas every store wants | `migrations` |
| `migrations` | the alembic plumbing a package's `strata-<name>-migrate` command runs: `require_current`, `stamp_if_new`, `migrate_main`, `run_alembic` | `migrations` |
| `service` | `serve(build, prog, port, error)`: the bootstrap a package's HTTP service starts from | `service` |

**Schema changes are migrations.** A database a package creates is built
in one step and stamped current; an existing one is brought forward with
alembic and refused on open until it has been, in either direction. Each
package ships its chain and the command that runs it, so upgrading a
package and then its database needs nothing from a checkout.

## Tests

```bash
uv run pytest packages/common
```
