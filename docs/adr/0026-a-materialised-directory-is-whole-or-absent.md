# 26. A materialised directory is whole or absent, and reused only when its manifest proves it

**Status:** accepted

## The decision

A materialised version is reused only when its manifest reads, names the same
catalog and declares the same features. Otherwise it is rebuilt. Reuse is
checked before anything is fetched. A directory is staged and renamed into
place with the manifest written last, so a directory that has a manifest is
complete; cache entries are written under a temporary name and moved; leftover
staging is an interrupted fetch and is discarded. An unreadable manifest format
means rebuild, never a guess at its fields. Features are not part of a
version's identity: declaring one keeps the version and rebuilds the directory.

## Why the rule is one and lives in the catalog

It lived on the laptop and on the host, and drifted: the host's copy missed the
features rule and trained remote rounds without features while the laptop's
did not. A rebuild costs a fetch; a wrong reuse costs a round trained on other
data, and nothing raises. One implementation, called from both.

## Why reuse is checked first

Checking after fetching once meant pulling a whole dataset from object storage
in order to delete it.

## Why whole or absent

A directory that is partly written looks like a dataset to everything that
reads by listing. The manifest is written last and the rename is what makes the
directory visible, so a reader that finds a manifest has the whole thing. A
cache entry written in place could be cut short by an interruption and then
served as a hit forever, since nothing rehashes a cache entry to notice.

## Consequences

- A manifest from another catalog with the same name and number is every
  version after switching to a rebuilt catalog, and is rebuilt (record 0008).
- `fetched` is zero on reuse, so a caller can tell a cache hit from a transfer.
- Record 0007's account of the features incident should point here.
