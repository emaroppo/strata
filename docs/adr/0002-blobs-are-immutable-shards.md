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

**A bucket is what two machines can share.** Configuring an endpoint means
shards, and a bucket is what lets the machine that trains and the machine
that labels read the same bytes. A shard is 512 MB by default: big enough
that shards are few, small enough that one is a reasonable unit to fetch
whole. The backend asks three calls of its client, put, get and delete,
and no more. Narrow on purpose: it is what lets a test drive the backend
without a bucket, and what keeps boto3 an optional dependency.

**Designing from the local case does not generalise.** A directory bakes
in cheap random access and real filesystem paths, and a tar member in a
bucket can honour neither. So the local backend keeps three rules nothing
forces on it: write-once, no listing (after ingest the index is
authoritative), and no paths on the protocol — `path_for` exists on the
local class only, for the Label Studio mount and for the repack, the two
callers that need files on the host that ingested them; the blob server
(record 0013) is what makes the mount optional. Packing into tars later was
then a new backend rather than a migration.

## Two read paths, neither of which streams

`get` is one sample, sparse and random: a review queue's access pattern.
`fetch` is many, dense and bulk: what materialising a dataset uses. They
are separate so a packing backend can read a whole shard once instead of a
range request per member without callers arranging it, and it does: it
groups what it is asked for by shard and reads each whole, because pulling
one object once beats a range request per member when most of it is
wanted.

## Why links, and what they cost

A file materialised from a blob is the same immutable bytes, addressed by
the same content, so the two share an inode; otherwise every dataset
version would cost a copy of its samples. Where the filesystem will not
link, the bytes are copied: correctness never depends on the link, only
disk usage.

Ingest links too, so cataloguing a corpus costs no disk, and there the
trade-off is different and accepted. The source belongs to whoever put it
there, and editing it in place would change the catalog's bytes without
changing the checksum that addresses them. That is acceptable for an
archive nothing rewrites; the alternative is a second copy of the corpus.
Once the catalog is on its own drive, ingest copies through a temporary
name, so an interrupted copy cannot leave a short file at the address of
the real one (record 0026).

The local cache is content-addressed and shared by every read. A review
pool is every unlabelled sample, and those are by definition in no dataset
version; a sample already pulled for a dataset is already there for the
pool, and one pulled for the pool is there for the next dataset.

## Two orderings that make repacking safe

**A shard is uploaded before the rows naming it are committed.** The
reverse leaves the index pointing at an object that does not exist, which
no re-run can detect and no read can survive. Rows are held back until
their shard has landed, so the failure mode is duplicated bytes in a
bucket — recoverable, and cheap. This is also why the S3 backend has a
`flush` and the local one does not: a member's offset is only known once
it has been written, so packing has to finish before the object exists.

**Samples are packed in ingest order, which keeps a group together.** A
corpus is walked directory by directory, so the frames of one video arrive
together and land adjacent, and materialising reads whole objects rather
than scattering range requests across the corpus; a resumed run repeats
the same order. Adjacent, not co-located: a group larger than a shard
still straddles two, and honouring group boundaries would mean partly
filled shards for a benefit that bulk reads do not need.

## A repack resumes from the index, deletes nothing, and checks a sample

There is no progress file to fall out of step with the index. A packed
sample's container sits under the target's prefix and a local one's
begins with two hex characters of its checksum, so the two cannot collide,
and what is left to pack is read from the index: a re-run resumes rather
than packing everything a second time. Nothing is deleted, because the
source keeps its copy and that copy is the rollback.

A member's offset goes into an INTEGER column, which Postgres caps at
2^31-1. A shard larger than that is refused rather than trusted to stay
under the default, since members past the limit would be recorded at a
wrapped offset and read as the wrong bytes.

Afterwards a sample of members is read back and hashed, every shard
represented, rather than all of them: sixty thousand members is sixty
thousand range requests, and what this looks for, an off-by-one in offsets
or a backend ignoring `Range`, is systematic and shows up in the first
few. A fault is likelier per shard than per member.

## A store is proved on a sample, against its row

Whether a host can reach its store is proved on a sample the catalog
holds, hashed against the checksum its row carries. A synthetic blob
written and read back passes against a store that cannot read the samples
at all, a wrong prefix or a bucket holding another catalog's shards, so it
is only the fallback for a catalog with nothing in it yet. The read back is
the part worth having either way: object storage that ignores a `Range`
header returns the start of the shard for every sample, which reads as
data rather than as an error.

## Removal is a fact about samples

Discarding a batch of bad pictures is a fact about the samples, not about
what was said of them. A removed sample is tombstoned and leaves every
reader: the queue, the labelled set, any version frozen from then on. Its
annotations leave with it, since they hang off a sample nobody reads any
more. The history stays, and so do the bytes, because shards are immutable
and compaction is what reclaims them. A version already frozen keeps its
members, because it is a record of what was trained on (record 0003).

A removal names what it removes, by collection, metadata or checksum. An
empty selection would name the whole catalog, and removing a whole catalog
is not a thing a command should be able to mean.

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
