# 52. A sample is its bytes and its type

**Status:** proposed; amends record 0001

## The decision

A sample's identity is its checksum **and** its type: the media and the
stored subtype path (record 0010). Within one type, samples still dedupe
by checksum: the same bytes ingested twice as `text/email` are one
sample with two origins. The same bytes as two types are two samples,
each with its own collections, metadata, origins and annotations.

Every reference that names a sample from outside the index names both:
a list member, a manifest entry, an answer carried between catalogs, a
Label Studio task. It names both always, not only where two rows share
a checksum.

The bytes are stored once per checksum, as now, and every row over them
shares the blob. Removing one row never reaches another's bytes.

## What this amends, and why

**Record 0001 made the checksum alone a sample's identity.** That
assumed the bytes say everything a sample is. Record 0053's types break
the assumption. An SFT example's bytes are only its target, the input
being metadata, so a masked message as an SFT example
(`text/sft/phishnet`) and a LoRA output that reproduces it word for word
(`text/generated/phishnet-email`) are the same bytes. They are not the
same sample: one is training data with a person's verdict on it, the
other is a model's output to be judged as output. Under 0001 the second
would have to be recorded on the first, and its verdicts, collections
and lineage would mix with the training sample's. Or it would be
refused, and the output lost.

What 0001 argued for is kept. A reference still survives a repack,
because it names the content, not a location. It still means the same
in every catalog, because the type is a name every catalog resolves the
same way. Ingest is still idempotent, because a type and bytes already
catalogued return the existing row.

## Why the type is part of every reference

"The checksum, plus the type where it is ambiguous" would be two rules,
and the second would show up only after a collision, in whichever
reader met it first. A reference that names both is never ambiguous. A
reader that finds no sample of that type and checksum says so, rather
than settling for the one row it can find.

Older references carry no type. The migration fills it in from the
sample row, which is unambiguous, since before this record no two rows
share a checksum. Two exceptions are tolerated rather than migrated:

- **A Label Studio task pushed before this record.** Its data holds a
  checksum and nothing else. It resolves while one live sample has that
  checksum, and is refused with the task id once there are two. Pushing
  again gives it the type.
- **A manifest written before this record.** `ManifestSample` gains a
  `type` defaulting to null. A reader matching an old manifest against a
  catalog matches on the checksum where it is unambiguous and refuses
  where it is not. The manifest's format does not change, since an older
  reader ignores a field it does not know and misreads nothing
  (record 0004).

## Why removal never reaches shared bytes

Removal is a tombstone, and the bytes stay, because shards are
immutable (record 0002). So removing a generated output leaves the
training sample with the same checksum exactly as it was, bytes
included. Raw files already share blobs with samples (record 0045), so
this is not new, but it becomes a rule for the compaction pass nothing
has built yet: a blob is reclaimed only once no live row of any kind
names its checksum, whether a sample of any type or a raw file.

## What stays keyed by the checksum alone

- **The blob store and blob paths.** One copy per checksum, served by
  checksum. The blob server needs only the bytes, and any row over them
  locates them.
- **Predictions.** A prediction is a function of the checksum, the run
  and the feature digest (record 0006). The same bytes give the same
  prediction whatever the type, and the feature digest already covers
  whatever metadata a model reads.
- **Materialised files.** A version holding both rows of one checksum
  writes one file, which both manifest entries point to.

## One rule a freeze gains

A version may hold two samples with the same bytes, if its collections
cover both types. They are then grouped by checksum when the split is
drawn, so the same bytes never sit on both sides of it. It works like a
video's frames under `group_by` (record 0023), with the checksum as the
group. Unlike a `group_by` key, which a version opts into, this grouping
always applies. The same bytes on both sides is a leak, whatever else a
version says about grouping.

## Consequences

- **`sample`'s unique constraint becomes `(checksum, media, subtype)`,**
  in a migration. `ix_sample_subtype` already covers the lookup by type.
- **`list_member` gains `media` and `subtype`,** filled by the migration.
  `strata-catalog lists put` takes the type for the whole list, since a
  list is chosen within one type in practice. A list file that names
  both is a later extension.
- **`by_checksum` takes the type.** Its callers are the blob server,
  which doesn't need it (any row will do), the answer merge, and the
  Label Studio sync, which reads it from the task.
- **Carrying answers between catalogs matches on checksum and type.**
  An answer whose type the target does not hold is reported as unknown,
  as an unknown checksum is now.
- **`ManifestSample` gains `type`,** written by every catalog from now
  on.
- **Record 0001 is marked amended,** with this record's reasoning.
