# 13. Label Studio stops at the adapter, and a URL is a credential

**Status:** accepted

## The decision

Everything that knows Label Studio's shape stops in one module. Past it a
sample is a catalog row and an annotation is a `strata.labels` value;
inside it, results carry control names, media keys and percentages. A
task refers to its sample by a URL that names the checksum, read and
written by one object so the two directions cannot disagree. Samples
reach a reviewer's browser through a blob server over signed URLs, with
expiries rounded to a window.

## Why a boundary

Label Studio's format is one annotation tool's wire format. When the
project's dataset file stored canonicalised Label Studio results, it was
storing a vendor format in a permanent record — and the scrubbing of
volatile fields on the way in was the tell. As a storage format for a
durable catalog it would shape the catalog by a replaceable UI. The
labeller keeps only what is Label Studio's: the config it generates, the
key a task is read from, the conversion at the edge. Media is a wire
concern there; what a file *is* belongs to the catalog (record 0010).

## Why one object for addressing

A URL written one way and read another silently orphans every task, and
that failure surfaces as an empty export rather than an error. Two forms
coexist on purpose: the local-files path is what Label Studio serves off a
mount and what every task created before the serving API uses; an HTTP
base URL is what replaces it. Reading accepts both, so the changeover is a
setting rather than a migration, and old tasks keep resolving until they
are relinked. The mount's prefix is a directory name reviewers' tasks
already point at, so changing it orphans them, which is a relink rather
than a rename. It is per catalog (`blobs_prefix`, "blobs" by default), since
two catalogs are two mounts; the deployment that predates that keeps
"images" in its config rather than in the code.

## Why signed URLs, and why the expiry is quantized

A browser loading an image cannot carry an Authorization header, so
whatever authorises the read has to be in the URL: the URL is the
credential, and it has to be worth no more than the one sample it names.
The signature covers the checksum and an expiry and nothing else, so a
leaked link authorises one blob and says nothing about any other.

A signature over a per-request timestamp would produce a different URL
for the same image every time, so a browser could never reuse a cached
copy and a reviewer would re-download every image on every push. Rounding
the expiry up to a window boundary means the same blob signs to the same
URL for the whole window, which is what makes the cache work at all. The
cost is that a link stays valid until the end of its window rather than
for exactly the requested lifetime.

## Consequences

- The blob server has one endpoint. Anything that answers questions about
  samples belongs in the query layer; mixing them would make the thing
  serving a review queue also the thing a training run depends on.
- Task creation is chunked: a first import on a real corpus is tens of
  thousands of tasks, and a chunk that fails leaves the ones before it
  created, so the map is returned as it goes and a re-run skips what
  exists. The client returns the map rather than caching it, because the
  catalog knows what a sample is and the client should not.
- `relink` re-signs a queue that outlives its window, and moves tasks off
  the mount onto the server, which is what lets the mount go away.
- The catalog issues the URL its server verifies. The labeller asks the
  catalog's configuration for signed URLs and never sees the secret, so
  the two halves of the credential cannot drift apart across packages
  (record 0015).
