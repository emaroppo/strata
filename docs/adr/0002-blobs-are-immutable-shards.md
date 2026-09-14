# 2. Blobs are immutable shards, and the local backend behaves like one

**Status:** accepted

## The decision

Samples' bytes are packed into tar shards in S3-compatible object storage,
with the catalog's `(location, offset, length)` as the only index. The
blob interface is shaped for that even though the first implementation is a
directory of files: a file is a shard of one, at `(relative path, 0,
size)`. Writes are write-once, nothing lists a backend, and callers get
bytes or a location, never a path.

## Why shards, and why the local backend pretends to be one

**Per-object storage is the wrong shape at volume.** At a few hundred
thousand samples the per-object overhead and the cost of ever listing a
bucket dominate. Tar has no index of its own, so the catalog's three
columns are the index, and because a tar member's bytes are contiguous, one
sample is one HTTP range request.

**Designing from the local case does not generalise.** A directory bakes
in cheap random access and real filesystem paths, and a tar member in a
bucket can honour neither. So the local backend keeps three rules nothing
forces on it: write-once, no listing (after ingest the index is
authoritative), and no paths on the protocol — `path_for` exists on the
local class only, for the Label Studio mount and for the repack, the two
callers that need files on the host that ingested them; the blob server
(record 0013) is what makes the mount optional. Packing into tars later was
then a new backend rather than a migration.

## Two orderings that make repacking safe

**A shard is uploaded before the rows naming it are committed.** The
reverse leaves the index pointing at an object that does not exist, which
no re-run can detect and no read can survive. Rows are held back until
their shard has landed, so the failure mode is duplicated bytes in a
bucket — recoverable, and cheap. This is also why the S3 backend has a
`flush` and the local one does not: a member's offset is only known once
it has been written, so packing has to finish before the object exists.

**Samples are packed in group order.** Frames of one video land adjacent,
so materialising reads whole objects rather than scattering range requests
across the corpus. Adjacent, not co-located: a group larger than a shard
still straddles two, and honouring group boundaries would mean partly
filled shards for a benefit that bulk reads do not need.

## Consequences

- A shard is never appended to. New data is a new shard; removal is a
  tombstone in the index and a compaction pass nothing yet needs.
- Copying an index (`strata-catalog copy`) leaves the bytes untouched, and
  repacking leaves the *content* untouched and rewrites where it lives.
  They are the two halves of the same property.
- The source of a repack must have real files behind it, because packing
  reads paths. The reverse direction — shards back to files — is what
  `materialise` already is.
- Materialising links what the host already has: a local blob directory is
  a cache consulted before the backend, and a hit costs a hard link.
