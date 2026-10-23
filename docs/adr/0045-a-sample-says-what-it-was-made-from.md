# 45. A sample says what it was made from, and what it was made from is kept

**Status:** proposed, revised three times (see Revisions); amends records 0010
and 0040, extends record 0022.
How a preparation is declared is record 0046, where it runs is record
0047, and what counts as an answer is record 0048.

## The decision

Raw files enter a catalog **as they are**, in a step of their own. Every
file is a **raw row**: its collection, its path under the ingest root,
its checksum, its location, and the ingest run that registered it. Its
name is `collection/path`, and no two raw rows share one. Raw rows are
append-only. Each blob is stored once, however many raw rows name it.

Samples are made from raw files by a **prepare run**. A run is handed a
list of raw files and a spec. The spec names a chain of stages, and the
run writes the chain's output into a collection (record 0046). Which
files to prepare is chosen outside the catalog.

Every sample has one **origin row** for each input it was made from, in
each run that made it. The input is a raw file or another sample. Each
origin row is one hop, and lineage is the chain of those hops.

Each run records:

- its producer and code identity;
- its spec, canonicalised and hashed;
- the files it was given;
- its counts, per reason, under the names its stages choose.

Runs live in the catalog, apart from modelling's run store. A run
supersedes another only for the inputs it states it continues.

Training-time choices are not made at preparation. A fact such as a
message's HTML tag count or its length goes into metadata. What a
dataset version leaves out is chosen when it is frozen.

A run that reads predictions or answers names the runs it read, so what
it read stays fixed.

## What this amends, and why

- **Record 0040 made the prepared index the only way into a catalog.
  Raw files now enter by an ingest of their own, and samples by prepare
  runs over them.** A prepared corpus left its raw files outside the
  catalog. They could be deleted, and then the corpus could never be
  prepared again: that is what happened to phishnet's Podesta mail. The
  index's purpose, declaring a corpus rather than guessing it, is kept.
  The spec now does the declaring.
- **Record 0040 admitted a file by its extension. A run is now handed
  the files it prepares.** Every Enron maildir file is named like
  `inbox/6.`, which has no suffix, so no extension could admit it.
  Choosing files is left to whoever runs the preparation, with whatever
  tool suits. The catalog does not grow a query language for it. How a
  type's `Metadata` contract applies to a sample with several origins is
  record 0049.
- **Record 0010 had a canonicalised text record its original's checksum
  in metadata. The original is now a raw row and the canonical text's
  origin.** Provenance in metadata is erased by the next ingest that
  sends fewer keys, and nothing reports it. So it moves to a structure
  the catalog owns. The `source_checksum` and `canonicalised` keys stop
  being written.
- **Record 0022 is extended, not changed.** A collection still says
  where a sample came from, and every query still names its
  collections. Raw rows have collections of their own.

## Why a collection is not enough

A collection says *where* a sample came from: `sat_images/2024-batch`,
`enron/single` (record 0022). It cannot say *from what*. A frame came
from a video, a message from a mailbox file, a training record from a
message and a template. The catalog had no place for that answer, so each type
made one up:

- `Frames` requires a `video` metadata string.
- Text stored in canonical form records `source_checksum`.
- The emails demo keeps its source path in metadata.

All three live in the free-form `metadata` column. Re-ingest replaces
that column wholesale, so a run that passes fewer keys erases the
provenance a previous run recorded, and nothing reports it.
`image-folder` records no metadata at all, so a catalogued image cannot
even say what file it was.

`strata-feature-store` answered this from the start: keep the raw
release, run a versioned standardise step over it, and record the
lineage on every operation. The catalog is the half of strata that
never did. Phishnet shows what that costs. Its cleaning wrote each stage
into a Mongo collection, often the one it read from. Today no code in
its repositories produces the corpora it trained on. And the
Podesta source files are gone, so that corpus can never be cleaned
again.

## Why raw files are kept, and kept as rows of their own

A corpus can be prepared again only if the files it came from outlive
the directory they arrived in. So the files a preparation uses are
ingested, and the catalog keeps them. Which files to ingest is chosen
outside the catalog, as which to prepare is: `strata-catalog ingest`
takes the same kind of list a prepare run does (`--files`), and without
one it ingests everything under its root. Ingesting more later is
another ingest that adds rows, and a name it already holds with the
same bytes is skipped. A prepare run handed a name nobody ingested is
refused, so a file left out cannot be prepared by accident.

Phishnet ingests the Enron maildir files its single messages come from,
about thirty thousand of 517,401, and adds the multipart and forwarded
files when it prepares those. Its Podesta mail, which survives only as
Mongo documents, is exported and ingested the same way: the single
messages now, the multipart and forwarded ones when a message model can
hold them. Until then those have no copy in the catalog, and the Mongo
dump is the only one. A raw file can also be prepared by several
projects, into different samples.

A raw row is not a sample. A sample is something strata can label: its
type admits it, holds it to a `Metadata` contract (record 0040), and
lets it into a queue or a dataset version. A raw file is often none of
these. A video is not frames, and a JSON export is not a message.
Making raw files samples would need a sample type for every raw format,
existing only to be stored.

There is one blob store, and a raw file's bytes go into it exactly as a
sample's do (record 0002). A local catalog hardlinks by checksum. Object
storage keeps an immutable tar shard. `repack` moves blobs from the
first to the second. The store holds one copy per checksum. Ingest looks
the checksum up before it puts, and so does writing a sample. A JPEG
ingested as-is is therefore one blob with a raw row and a sample over
it.

The same bytes under several names are several raw rows: Enron files
the same message under `inbox/`, `all_documents/` and
`discussion_threads/`. A raw row's checksum is therefore not unique, and
`repack` updates every row that shares a location. That is the intended
design, and its cost is accepted.

A raw row's name is its collection and its path under the root the
ingest was given, such as `enron/maildir/quenet-j/inbox/6.`. The two are
kept as separate columns, because a collection can have several segments
and a name alone would not say where it ends. A raw row therefore
belongs to exactly one collection. The same bytes ingested into another
collection are another row over the same blob. A name means one set of
bytes:

- **Ingesting a name again with the same bytes** writes nothing, so an
  interrupted ingest can simply be run again.
- **Ingesting a name again with different bytes** is refused, with the
  files listed. A changed source goes into a new collection.

**Known limit:** a shard member's offset and length are 32-bit (the
repack's guard, `MAX_SHARD_BYTES`). A single file over 2 GiB can be
neither a sample nor a raw file. Widening those columns is its own
migration, deferred until a corpus needs it.

## Why ingest and prepare are two steps

Ingest is a one-off: files go into the catalog's store, and raw rows are
written. Preparation is repeated. Rules change, and a second project
wants different samples from the same files. Joining the two would
re-upload a corpus on every change of rules. It would also make "which
files exist" depend on "which files a preparer accepted".

Neither step belongs to a project. A raw collection serves every project
that prepares from it, and a sample can be in several projects through
its collections. `project.toml` selects sample collections, as before.
A spec is a file in the repository of whoever prepares the corpus. The
catalog stores its canonical content, never its path, because a path
says where a file sat and not what it said (record 0037).

When the files and the stages are on the same machine,
`strata-catalog ingest --prepare <spec>` does both in one pass:

1. It hashes the files and runs the chain on them where they are. It
   prepares exactly the files it ingests.
2. It packs the raw blobs and the sample blobs into the same shards,
   and uploads once.
3. It commits both runs in one transaction.

It must write exactly what the two steps would have written. The
conformance suite checks this by doing both on one corpus.

## Why a run is handed its files

A prepare run is given a file of raw names or checksums:

```bash
strata-catalog prepare specs/enron-single.toml --files list.txt
```

Choosing them is not the catalog's business. Phishnet's single messages
are chosen by a script that reads `file_path` from Mongo. That script
goes away once threads are prepared, and the spec does not change. Any
other selection is a `grep`, a script or a notebook away. A query
language in the catalog would be one more thing to design and keep, for
a choice that a list already records exactly. `strata-catalog raw ls
<collection>` prints a collection's names, so that "all of it" is one
pipe away.

A name that matches no raw row is refused, and the refusal lists every
such name. `--allow-missing` counts them instead. The run records the
list's digest and the checksums it resolved to. The rows collapse to
distinct checksums, each prepared once, and the run reports both
numbers.

## Why a stage reads a checksum, not a path

A prepare run's input is a set of raw checksums. The framework turns
each checksum into a local file named `<checksum>.<ext>`, using the
first of these it has:

1. the original file, if a combined pass was given it and its hash
   matches;
2. a hardlink from the local blob store;
3. the blob cache (`STRATA_BLOBS_CACHE`);
4. a batched download from object storage.

A catalog on one machine never fetches anything.

The first stage reads that file's bytes. A stage that wants the names
the file arrived under is handed them as context, but no name is
privileged. A checksum is prepared once, however many raw rows name it.

What a filename used to carry moves elsewhere:

- **Admission by extension is replaced by the list a run is given.**
  Extension can't do the job anyway: every Enron maildir file is named
  like `inbox/6.`, which has no suffix at all.
- **Provenance metadata such as `source_file` is replaced by origin
  rows.**
- **Grouping by directory is replaced by grouping on the origin.**
  `Frames.video` no longer needs to be required metadata.

## Why an origin row per input, and not a column on the sample

One sample can come from several inputs:

- **The same input file under several names** gives one checksum and so
  one call. Deduplication happens before preparation.
- **Different files that yield the same body give one sample.** A message
  exported to JSON and the same message read from the maildir are an
  example: one sample, two origin rows.
- **One input gives many samples.** A video gives frames, and a thread
  gives its messages.

A single parent column holds none of these but the last. So the record
is a row per (sample, run, input). The input is a raw checksum or a
sample. That is the whole graph: each row is one hop, and lineage is the
chain of hops.

A sample made from samples says so the same way. A training record has
two origin rows, one for its message and one for its template. The
annotations and predictions it was made with are named in its run's
spec, not in its origin rows (see "what a run read", below).

## Why counts, not a reason per input

A run records counts per reason, under the names its stages choose. One
project's `thread` is another's `html`, so a fixed list of reasons would
fit no corpus. Nothing is recorded per left-out input, and that is
enough to verify a run:

- **Which inputs produced nothing.** Origin rows say which inputs did.
  The files the run was given, minus those, are exactly the ones that
  did not.
- **That nothing was lost.** Inputs are counted by checksum: the
  distinct checksums the run was given equal those with at least one
  origin row, plus those an earlier run with the same chain had already
  prepared (and so were not run again), plus those that produced
  nothing. The run counts the second
  group itself as it goes, under the stage that left the input empty,
  rather than deriving it by subtraction, which would make the equation
  true by definition. A crash, or an input lost without a trace, breaks
  it. The equation holds however many samples one input splits into. A
  sample a stage drops from an input that still produced others is not
  in it; that is a count per stage, kept for information. Counting the
  samples' checksums instead would not add up, since two inputs can
  yield one sample and one input can yield many.
- **Why one input was dropped.** The chain is deterministic per input,
  so running it on that one input gives the reason.

The files a run was given are recorded as the checksums they resolved
to, with a digest that lets `verify` confirm the set. Raw rows are
append-only and a name never changes its bytes, so the record stays
true.

## Why training-time exclusion is not preparation's business

A message whose body carries HTML tags is still a message, and a long
one is still a message. A preparation that skipped them would decide
what the durable asset holds, by a threshold chosen for one model's
window. The emails demo's preparer did exactly that (its own comment
calls the cap "the reverse of the architecture's stance"). Every
project then inherited a choice it never made.

So the sample is kept, and the facts that decide such a thing are
recorded on it. `html_tags`, `characters` and `word_count` are facts
about the bytes, which the sample type computes (record 0049). Leaving
the sample out is a choice made when a dataset version is frozen, by a
condition on those facts in the version's selection spec (record 0050).
The version records the spec and exactly which members it has, a run
records the version it trained on, and the freeze counts what it left
out (record 0036). A stage filters only what
cannot become a sample of its type at all. A mail with no text in its
body is one example. It is counted.

## Why supersession is stated per input

A later run may produce, from an input an earlier run already prepared,
samples the earlier run did not. Take a message prepared as a single
message that turns out to be a thread. Once a multipart run splits it,
which samples does a project see?

"Whatever ran last" would answer that quietly, and strata takes no
default of that kind. A query names its collections (record 0022). A
round continues a parent only by a policy its caller states (record
0025). A grid runs cold or from one named parent (record 0037).

Two cases need nothing stated:

- **A different set of files** simply adds samples. Phishnet's multipart
  messages come after its single messages.
- **The same spec over files it already prepared** writes nothing new
  for them. The chain is deterministic, so the samples already exist.
  A full run after a narrowed one only adds what the narrowed one left
  out.

"The same spec" means the same chain, not only the same text. Two runs
have the same chain when their canonical specs hash the same, each stage
has the same version, and every rule file the chain reads has the same
digest. A rule file edited in an editable install changes what the
chain does without changing the spec's text or a package's version, so
the spec hash alone would call two different chains the same. A run
that writes nothing new is still recorded, with its counts, so that the
attempt shows in the history.

Only **a different spec over files another run already prepared** needs a
statement. A changed rule file, or a multipart chain over files a single
run prepared, are the cases. So such a run states the run it
**continues** (`--continues <run>`), and continues the whole line of
runs behind it. The statement belongs to the run, not to the spec: a
spec says what a chain does, and naming a run in it would make the same
chain hash differently each time it continued another. For each input both runs prepared, the continuing run's
samples are current and the earlier run's are not. For each input only
the earlier run prepared, its samples stay current. A run in this case
that states nothing is refused before it writes, and the refusal names
the run it overlaps.

Nothing is deleted, rewritten or invalidated (records 0006, 0037). The
superseded samples, their annotations and every frozen version that
pinned them stay as they were (record 0003). The run counts what it
superseded, and how much of that carries a human answer. A span does not
follow to a successor sample: its offsets point into the old text
(record 0010). Carrying it over is a remap with its own run, and it
counts what did not survive.

## Why a run names the runs it read

Making a training record from a message reads several things:

- the message, and the template;
- the disclaimers and footers marked on the message, so that the
  record's text can leave them out;
- a person's corrections to those marks, where a person made any;
- predictions, where a model's output goes into the record.

Its origin rows name the message and the template. Its run's spec names
the rest:

- the import run that marked them, and any judge run, by id;
- prediction runs by id;
- human answers as the label set stood when the run started.

Every one of these is fixed. Predictions are never invalidated, a run's
annotation rows are never changed, and a correction is a new row with a
later time. So naming a run pins exactly what was read, and a later
correction moves nothing that was made before it.

## Why runs live in the catalog, apart from training runs

Training runs live in modelling's run store (record 0005), one per
project and one per host. Ingest, prepare, import and judge runs live in
the catalog, beside what they wrote. One shared table would make a
cleaning run and the checkpoint built on it a single join. The price
would be tying the catalog to a store it otherwise never needs. Their
ids are minted the same way, a timestamp with microseconds and a host
token, so either side can name the other's runs without coordination.
`copy` and `merge` can carry the catalog's runs too. They carry raw rows
by ingest's rule: a name the target already holds with the same bytes is
skipped, and a name it holds with different bytes is refused, with the
names listed.

`materialise` writes the ids and digests of the prepare runs behind a
version's members into the manifest. That is a manifest format change
(record 0038). A training run then records which preparations its data
came from. `strata-catalog verify --run <id>` checks four things:

- the digest of the files it was given;
- the count equation;
- that everything the run wrote is present;
- with `--deep`, that it still hashes to its checksum.

So a training run can show that the preparation it depends on is the
one it trained against, without either store reading the other.

## What this rules out

- **Provenance in metadata.** `Frames.video`, `source_checksum`,
  `canonicalised` and `source_file` stop being written. Metadata keeps
  facts about the sample, and a grouping key (record 0023) can be
  derived from the origin.
- **A sample with no recorded origin**, from now on.
- **Training-time choices at preparation.** No length cap, and no HTML
  skip.
- **An implicit current.** Recency never decides what a project sees.

## Consequences

- **New tables:** `raw`, `run`, `run_input` (one row per distinct
  checksum a run was given, since a list can run to hundreds of thousands)
  and `origin`, whose input is a raw checksum or a sample's. The run row
  records the chain's identity and the run it continues. The `run_id` on
  `annotation` that record 0048 adds comes in the same migration. They come in one alembic migration
  for both dialects
  (record 0021). A store at the old head is refused, not upgraded in
  passing (record 0018).
- **Rolling it out** means migrating every catalog database a host
  holds, and rebuilding each blob server to the matching revision,
  because the server checks the revision exactly at startup.
- **Existing catalogs get their origins filled in** by a backfill run,
  recorded as the backfill it is. It registers the raw files that can
  still be found, links them from what the metadata says (`source_path`,
  `Frames.video`), and counts what it could not link.
- **The commands that ingest, prepare, show lineage and verify** are
  `strata-catalog`'s (record 0047). `strata-catalog raw ls
  <collection>` prints a collection's names.
- **A sample's metadata is combined from its origins** (record 0049).
- **`prepare-email` keeps every header, and records HTML as a tag
  count.** The emails demo's decision to remove HTML mail (its record
  0003) becomes a filter applied when a version is frozen.
- **Labels move between catalogs** through an import run. It matches
  samples by checksum, keeps each answer's source and history, and names
  the source catalog's identity. A span whose sample has different bytes
  in the target does not transfer by checksum. A remap run can carry it
  where the difference between the two texts is known, and it counts
  what it could not carry.

## Open questions

- **A label that refines a label**, such as a name's form or its
  grouping, with a pointer to the answer it refines. It is set aside
  with entities (`docs/proposals.md` §17).
- **The optional `blob` table.** If raw and sample rows both pointed at
  one checksum-to-location row, `repack` would update a single row.
- **When to port `prepare-video` and the folder preparers** to stages.
  `Frames.video` stays required until they move.

## Revisions

- **Ingest is handed its files, as a prepare run is (revised after the
  first commit).** This record said every file is ingested, not only
  those a preparation uses, and gave the whole Enron maildir as the
  example. The user chose to ingest only what phishnet prepares, for
  now: the Enron files and the Podesta documents its single messages
  come from. Multipart and forwarded messages wait for a change to the
  message model. Keeping every file guards against a source being lost,
  and that risk differs by corpus: the maildir is public and kept on
  disk, while the rest of the Podesta export stays only in the Mongo
  dump. So which files are kept is a choice made per corpus, outside the
  catalog, with the same list a prepare run takes. Nothing else changes: raw rows are
  still append-only, a name still means one set of bytes, and ingesting
  more later adds rows.
- **A run, not its spec, names the run it continues (revised while it
  was built).** This record said a spec states the run it continues.
  Building it showed the cost: the spec's hash and the chain's identity
  would change with the run named, so one chain would look like several.
  The spec says what the chain does, and the run says what it replaces.
  The count equation gains the inputs skipped as already prepared, which
  the first draft had no name for, and the new tables are listed as
  built.
- **The remap is part of the import run, and answers travel by file
  (revised while it was built).** This record had a remap run of its
  own carry spans to a sample whose bytes changed. Built, it is one
  import run: `export-answers` writes a label set's answers by checksum,
  with every row of their history, and `import-answers` reads that file,
  matching by checksum or through a pairs file of old and new checksums.
  One run keeps the answer, its history and its remapped spans in one
  transaction, so a sample is never left with its history moved and its
  answer not. A file is also the only way between catalogs at different
  revisions, since a store at an old head is refused (record 0018).
  Answers on removed samples stay behind, as everything a removal
  touches does.
