# 22. A collection is where a sample came from, and every query names the ones it draws from

**Status:** accepted; amended and extended by record 0050 (proposed)

## The decision

A sample belongs to one or more collections, one row per collection, and
collections are added, never replaced. Every sample query names the collections
it draws from; "all of it" is a marker a caller chooses on purpose. A
collection path covers what is under it and never a sibling that merely shares
a prefix. A project declares its collections, and dropping one declares that
data out of scope, training included.

## Why one row per collection

The same images feed more than one job, which is the reason a catalog is worth
keeping at all. A corpus is reusable across jobs rather than owned by the first
one to ingest it, so re-ingesting under a second collection adds a row and
disturbs nothing.

## Why every query names its scope

Forgetting to scope is how a review queue once filled with another project's
data. With no default, the omission is a type error rather than a silent
widening. `sat_images` covers `sat_images/2024` and never `sat_images_old`,
which a bare prefix match would swallow; the distinction is decided once, in
the query builder, not at each call site.

## Why dropping is a declaration

Carrying a dropped collection quietly would move the metrics without anyone
having decided to. To stop being asked about a batch while keeping what it
already answered, skip the rest of it instead; the two are different acts and
the catalog keeps them apart.

## Consequences

- `unlabelled` and `labelled` are per label set and per collection, so several
  jobs' data is never offered to every job.
- Samples in no collection are reachable only through the marker, which is what
  keeps an accidental ingest out of every project's queue.

## Amendments

- **A membership row has an id and a time (record 0050, proposed).**
  Running a version's selection spec again needs to know which
  collections a sample was in when it was frozen. Collections are only
  ever added, so the rows in id order are the whole history.

- **A selection spec need not name its collections (record 0050,
  proposed).** It names its sample types, which are already a scope,
  and its collections only if it wants them. The rule stood because a
  queue once filled with another project's data unnoticed. A spec's
  scope is written in it and recorded on the version, and the freeze
  counts its candidates by collection, so a wider selection is visible
  rather than silent. Every other query still names its collections.
