# 1. A sample is its bytes: every reference that must survive a move is a checksum

**Status:** accepted

## The decision

A sample's identity is the sha256 of its bytes. Anything that refers to a
sample from outside the index — a Label Studio task URL, a prediction-cache
key, a blob's path under a local root, a manifest entry — names the
checksum, never the sample's integer id and never where its bytes happen
to sit.

## Why the checksum and not the id or the location

**A location moves.** Files become tar members in a bucket when a catalog
is repacked, and repacking rewrites every `(location, offset, length)` in
the index. A task URL created months earlier does not change, so a URL
built from a location is orphaned by the first repack, and the symptom is
an empty export rather than an error. A URL built from the checksum keeps
resolving: `by_checksum` is how a task is recognised on the way back.

**An id is local.** The integer primary key is right inside one catalog
and meaningless outside it (record 0008). A cache keyed on it would be
wrong the moment a second catalog existed; the bytes are what the model
actually saw, and they are the same bytes everywhere.

**Content addressing makes ingest idempotent.** A file whose bytes are
already catalogued returns the existing id, which is what makes re-running
`ingest` over a growing directory safe, and two identical samples under
two names cost one copy.

**It makes a served blob cacheable forever.** Content-addressed bytes never
change, so the blob server's response can carry a permanent cache header,
which is what keeps a review queue fast over a LAN.

## Consequences

- `blob_path(checksum, suffix)` is module-level and outlives the local
  backend: Label Studio serves off that layout, and it has to keep doing so
  after the bytes are also in a bucket. Two levels of fan-out, because a
  flat directory of a million entries is slow to stat.
- A materialised file is named for its checksum, not its container. When a
  tar shard held hundreds of samples, naming after the container gave every
  one of them the same filename — one file on disk, every manifest entry
  pointing at it, and a run over one image repeated with nothing to say so.
- The manifest carries the checksum beside the id, so files and labels
  alone are enough to train anywhere, and another catalog can match them
  to its own samples.
- Canonical form (record 0010) is what keeps the checksum honest: two
  documents that read identically must be one sample.
