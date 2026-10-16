# 45. A sample says what it was made from, and what it was made from is kept whatever it is

**Status:** proposed; extends records 0022 and 0040, takes over the
provenance half of record 0010

## The decision

Every ingest is a **run**, and a catalog records it. A run names what
produced it: the preparer or script, the version of that code, and the
canonical hash of its spec. A run is recorded even when it writes nothing
new. Raw inputs are kept as **sources**, whatever format they are in: an
mp4, a maildir file, an mbox, an HTML dump, a zip, a CSV. A source is
content-addressed in the same blob store as samples, but it is not a
sample. A **derivation** edge links a sample to each parent it was made
from, either a source or another sample, through the run that made it.
Edges are many-to-many, and each can carry attributes. The prepared index
declares all of this (format 3). The catalog refuses an entry whose parents
it does not hold. A later run over the same parents supersedes an earlier
one for the current view, and a frozen version keeps the samples it pinned.
Lineage has nothing to do with media: one table serves images, frames,
text and every plugin type.

## Why a collection is not enough

A collection says *where* a sample came from: `sat_images/2024-batch`,
`enron/single` (record 0022). It cannot say *from what*. A frame came from
a video, a crop from an image, a message from a thread file, a training
record from an email and a template. The catalog had no place for that
answer, so each type made one up:

- `Frames` requires a `video` metadata string.
- Text stored in canonical form records `source_checksum`.
- The emails demo keeps its source path in metadata.

All three live in the free-form `metadata` column. Re-ingest replaces that
column wholesale, so a run that passes fewer keys erases the provenance a
previous run recorded, and nothing reports it. Provenance is a fact about
how the catalog came to hold a sample. It needs a structure the catalog
owns, not a key a preparer may or may not remember to send.

`strata-feature-store` answered this from the start: source, then release,
then a standardise run, then output, with lineage written by every
operation. The catalog is the half of strata that never did.

## Why a source is not a sample

A sample is something strata can label. Its type admits it by extension
and holds it to a `Metadata` contract (record 0040), and it can appear in
a review queue or a dataset version. Raw data is often none of these
things. A video is not frames, a maildir file is not a message, and a
DNC HTML dump is not text anyone should label. If raw inputs had to be
samples, either every raw format would need a sample type that exists
only to be stored, or raw data would stay outside the catalog. Outside the
catalog, re-cleaning from the original becomes impossible as soon as
someone deletes a directory. The latter is what happened to the Podesta
corpus in phishnet.

So a source has a checksum, a blob location, a media type, the name it
arrived under, free metadata, and the run that registered it. It has no
type, no label set and no side. A file that is both raw and a valid sample
(a JPEG ingested as-is) is registered as both, with an identity edge
between them. Most image corpora take that path, and it costs nothing
extra: the blob is stored once, because blobs are addressed by checksum.

## Why every ingest is a run, and why that is not optional

The feature store's rule is that lineage is automatic and enforced by the
type signature. Optional lineage gets skipped, and the catalog drifts into
fiction. `Catalog.ingest` therefore takes a run and has no default.
`strata-labeller ingest` and `strata-prepare` open one for the caller.

A run's id is minted the way record 0005 mints a training run's id: a
timestamp with microseconds and a host token. That keeps runs unique
without coordination, so `strata-catalog copy` and `merge` can carry them
between catalogs.

The run records:

- its kind (`prepare`, `transform`, `export`, `import`);
- the producer, and the identity of that code: the package version, or
  the file hash for project-local code (record 0042);
- the spec as canonical JSON, and its hash (record 0017);
- the sources and samples it read;
- counts: written, already present, refused (record 0036).

A run that writes nothing because every output already exists is still
recorded, pointing at the existing samples. Re-running a pipeline costs
nothing, and the history shows that the attempt was made and changed
nothing.

## Why edges are many-to-many and carry attributes

Real derivations take every shape:

| Shape | Example |
|---|---|
| One parent, many children | a video into frames; a thread file into messages |
| Many parents, one child | the same message deduplicated out of three mailbox files; a training record made from an email and a template |
| One parent, one child | a canonicalised text from its original |

A single parent column on the sample cannot hold any of these except the
last. The facts that differ between occurrences of one sample belong on
the edge, not on the sample, because the sample is shared:

- a frame's index and timestamp;
- a crop's box;
- a message's mailbox, position in the thread, and `is_main`.

Edge attributes are free JSON, like sample metadata. A type can declare a
pydantic model for the attributes its preparer must supply, which is
checked the same way `Metadata` is.

## Why the index declares lineage

A catalog still takes a prepared corpus and nothing else (record 0040).
The preparer knows what each file came from, and the catalog does not.
Format 3 of `prepared.json` adds:

- a `run` block (producer, version, spec);
- a `sources` table of the raw files the run read, each with its path
  under the root;
- per entry, `derived_from`: a list of `{source | sample: checksum,
  attrs}`.

Format 2 is refused with a message, as every format change has been
(record 0038).

## Why a missing parent is refused

An edge to a parent the catalog does not hold claims a lineage the
catalog cannot show. Record 0005 drops such a link on merge for the same
reason. Ingest checks every `derived_from` checksum against the catalog,
or against the corpus's own `sources` table, before anything is written.
It refuses the corpus whole, listing every missing parent (record 0030).
This is also how cross-sample references become safe. A training record
that points at a prompt template is admitted only if the template is
already catalogued.

## Why supersession is per parent, and frozen versions do not move

A cleaning rule changes, and the same raw thread is cleaned again. The new
bodies have new checksums and are therefore new samples (record 0001).
The old samples are not deleted and are not wrong. They are what that
run's rules produced, and a frozen version may be built on them. "Current"
is therefore a view: for each parent and run kind, the children of the
latest run. A query asks for the current view or names a run. A dataset
version pins samples, never runs, so it resolves to exactly the data it
was frozen with (record 0003). This is the feature store's rule: a
correction is a new version, never an edit.

## What this rules out

- **Provenance in metadata.** The ad-hoc provenance keys stop being
  written: `Frames.video` becomes a source edge, and `source_checksum`
  and `canonicalised` become an edge to the original, now kept as a
  source. A grouping key stays in metadata (record 0023), but a preparer
  can fill it from lineage.
- **An ingest with no run.** No caller can opt out.
- **Retroactive lineage.** A sample ingested before this record has no
  edges, and that means *unknown*, not *no parents*. This is the same
  distinction record 0005 draws for a run that predates the per-sample
  record of what it saw. A backfill run may register the sources it can
  still find and link them, and it is recorded as the backfill it is.

## Consequences

- Three new tables, `ingest_run`, `source` and `derivation`, in one alembic
  migration for both dialects (record 0021). A store at the old head is
  refused, not upgraded in passing (record 0018).
- **Storage grows by the raw tier.** Sources go through the same blob
  backends, so `repack` shards them and Garage holds them as it holds
  samples. A run can mark its sources `transient` (registered, hashed,
  not retained). Lineage then still names them, and re-deriving from them
  is honestly impossible.
- **Removing a source** is a tombstone, like a sample (record 0002). It is
  refused while a sample in a frozen version descends from it, unless
  forced, and a forced removal is recorded.
- **`strata-catalog lineage <checksum>`** prints ancestors and
  descendants with their runs. `strata-catalog runs` lists runs.
  `materialise` writes the runs behind a version's members into the
  manifest, so a training run can name the cleaning spec behind its data.
- **Preparers move to format 3:**
  - The folder preparers declare each file as both a source and a sample.
  - `prepare-video` declares the video as a source and each frame as
    derived from it, with index and timestamp.
  - The emails demo's `prepare-email` declares the message file.

  `PreparerContract` gains a check that every entry's parents are
  declared.
- `copy` and `merge` carry runs, sources and edges, parents first.
  Record 0005 orders a run history by the same rule.

## Open questions

- **One run store or two.** Should ingest runs and modelling's training
  runs (record 0005) share one table? Sharing would make "the cleaning
  run behind this checkpoint" a join rather than a manifest field. The
  cost is coupling the catalog to the modelling store, which today stands
  alone.
- **Imports as runs.** Should a candidate-annotation import (record 0028)
  be a run of kind `import`, so that an annotation also says what made
  it?
- **Supersession key.** Is it per (parent, run kind), as proposed? Or per
  (parent, producer), so that two different cleaners can be current side
  by side?
- **When to port prepare-video and the folder preparers.** With this
  record, or in a follow-up? `Frames.video` stays required until they
  move.
