# 30. A command renders a record an operation returns, refuses before it writes, and prints nothing from the library

**Status:** accepted

## The decision

An operation, whether a catalog stage, an admin function or a labelling step,
takes a request and a context and returns a record: small enough for a ledger,
naming what it made and never embedding it. A request with an unknown key is an
error. The command line builds the request, calls the operation and renders the
record, or emits it as JSON, and it uses the standard library only. Library
code prints nothing: each step returns what it decided and what it left out,
and the command says it. A plan is computed and applied by the caller. A
command refuses before it writes and names what to fix. There is one console,
and JSON goes past it.

## Why records

The same operation is called by a command, by the orchestrator and by a test,
and only the command has a terminal. A record that names its output by
identity is what a ledger can key on and what a test can assert against; a
record that embedded a dataset would be a copy of it. A misspelled request key
that did nothing silently is the bug pydantic's strict models exist to refuse.

## Why the library prints nothing

A step that prints cannot be reused where there is nobody to read it, and a
step that hides what it dropped is how a corpus ends up quietly smaller. So
`scan`, `plan`, `relink` and their kind return decisions and omissions, and
the command renders them. Computing a plan and applying it separately is what
makes a dry run free and an interrupted apply describable.

## Why refuse first

A project's schema is built when the project loads, so a bad template fails at
load rather than mid-push. The host's catalog is asked before a version is
frozen, so a wrong host is reported before an orphan version exists. The
scoring run is asked for before the pool is fetched, one request now against a
pool scored before noticing. Undeclared labels are refused before the first
annotation is written rather than partway through.

## Why one console, and why JSON goes past it

Two console objects fight over the same lines and made the progress bar
flicker. A console wraps to the terminal width and colours, which is right for
a table and fatal for output piped into `jq`, so `--json` writes to stdout and
nothing else. Printed locations are redacted, because troubleshooting output
travels into chats and issues and the index URL carries the password.

## Consequences

- The catalog's install stays thin: no CLI framework in the package that a
  service imports.
- The modelling client and command follow the same rule for the same reason
  (record 0007).

## Amendments

- **The shared pieces are one implementation, in `strata.common.cli`.**
  Four commands each wrote their own JSON emitter and their own
  error-to-exit path, and they drifted: one lacked `default=str`, one
  swallowed `ValueError`, and the labeller printed refusals to stdout, into
  the JSON a program was reading. `emit` and `print_json` print the record
  whole on stdout; `run` and `exit_on` print a refusal on stderr and exit 1,
  and always also refuse a `Refused` and a store behind the code
  (`strata.common.errors`, record 0018), so a schema message written for a
  person is never a traceback. The labeller may not import `common` and
  matches the behaviour locally; it is also the one command built on typer
  and rich, which this record's "standard library only" did not state as
  an exception and now does, for the review queue's tables and progress.
- **Every command resolves the host file the same way**: `--config`, else
  `$STRATA_CONFIG`, else `./config.toml`, through
  `strata.catalog.config.settings_path`, which the catalog's own commands
  and its migrate tool had not been using (record 0019).
