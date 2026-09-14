# 20. A host holds several catalogs, and a project names its own; nothing falls back to the default

**Status:** accepted

## The decision

A host's `config.toml` may describe several catalogs, one of them the default.
A project names the catalog it draws from. Every command takes the project's
catalog configuration, and nothing falls back to the host's default in its
place: an unknown name is refused with the list of the ones that exist, and
several catalogs with no default is refused at the point of use rather than
resolved. A listing opens one catalog per project. Each machine reads its own
configuration.

## Why never the default

A job reading the wrong catalog reports real numbers about the wrong data, and
nothing raises. Two callers once signed task URLs with the default catalog's
secret instead of the project's, which was right on every host with one catalog
and wrong on a host with two, with nothing to say which. Five commands once
opened a local SQLite file whenever one existed, regardless of the configured
index, and after the index moved to Postgres they went on reporting counts from
a file nobody wrote to, and one of them trained on it. Choosing alphabetically
would choose a corpus by spelling.

## Why the project names it

Where a catalog is describes a machine; which catalog a job draws from is part
of the job, so it travels with the project and is a statement about the data.
A project moved to another host expects a catalog of the same name there, and
gets an error rather than someone else's corpus when there is none.

## Consequences

- Commands that run with no project take `--catalog`, and the operator names
  it, since `project.toml` normally does.
- A listing that counts samples opens each project's own catalog, because two
  projects on one host need not share one and counting both against the
  default reports numbers that belong to another corpus.
- A host that misses one catalog 404s on every image or refuses every round,
  which is the visible failure this trades a silent one for.
