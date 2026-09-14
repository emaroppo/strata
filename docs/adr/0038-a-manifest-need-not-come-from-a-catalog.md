# 38. A manifest need not come from a catalog, and null means the producer did not say

**Status:** accepted

## The decision

The manifest is the contract (record 0004), and a producer that is not a
strata catalog may write one. What it cannot say, it leaves null, and a reader
treats null as unknown rather than as a default. The dataset name and the
format are required of every producer. A format the reader does not know is
`ManifestFormatError`, distinct from a malformed manifest.

## Why null and not a default

A default would have the manifest claim something that is not true. Ratios
defaulted to a split that was never achieved would let a hand-written manifest
claim one; a defaulted version would give `report` an order to compare runs in
that nobody chose; a defaulted format would read a manifest from before the
field as the current layout, which is the one guess the field exists to stop.
So the version is null from a producer that does not version and `report`
compares nothing rather than guessing, ratios are null when nobody recorded
them, holdout ratios are null from a producer that does not hold out and from
every earlier version, and the sample id is null from a producer with no
catalog, the checksum being the identity that survives (record 0001).

## Why the name and the format are required

A warm start finds the previous run over the same dataset by name, so a
manifest without one cannot be trained from twice. The format is what a reader
refuses on, and a reader that could not tell an old manifest from a new one
would misread the old one silently.

## Why a format error is its own type

Stale means rebuild; broken means a bug. A caller has to tell the two apart,
and a `ValueError` says neither.

## Consequences

- The same rule holds outside the manifest: a frame's seconds are null when
  the container reports no frame rate, never a wrong number. It is kin to
  record 0008's "a nullable column means unknown, not no".
- A version materialised without a catalog has no `catalog_id`, and a host
  that serves two catalogs cannot resolve its lineage; that is the cost, and
  it is the producer's.
