# 23. A grouping is a metadata key, and a version names the one it respects

**Status:** accepted

## The decision

Nothing groups unless a dataset version names a metadata key in `group_by`. A
grouping is an ordinary key in a sample's metadata until then: a prepared
corpus records facts, such as which video a frame came from, and a sample type
declares no grouping. A missing or null key is its own group. One catalog can be
split by several groupings, one per version.

## Why a key and not a column

There was a `group_id` column, and it was one grouping respected whether or not
anyone asked. A satellite scene that groups by scene and carries coordinates
had nowhere to go, and a version that wanted frames ungrouped could not say so.
A key named per version makes grouping a decision the version records rather
than a property the catalog imposes; old versions record no key, which is true
of them. The migration that removed the column records why.

## Why re-ingest cannot disturb a version

A known sample is re-described on re-ingest, metadata included. Regrouping
cannot disturb a built version because membership and sides are materialised
when the version is frozen, not recomputed from the data.

## Consequences

- The manifest carries each sample's metadata, so a split can be drawn again
  from the directory under another key.
- A project's `group_by` is what keeps consecutive near-duplicate frames on one
  side of the split; the type does not enforce it, the version does.
- For an unprepared corpus, a directory per video is the convention that says
  which video; a prepared index says it as a fact.
