# 40. What enters a catalog is declared outside it, and a type's metadata is a contract

**Status:** accepted

## The decision

A catalog takes a prepared corpus and nothing else: a directory of files and a
prepared index, `prepared.json`, which names the sample type the corpus is and
every file to take, each with the metadata a preparer knew and any candidate
annotation it arrived with. A type declares what a sample of it must arrive
with as a pydantic `Metadata` model, inherited as the type is: `Frames`
requires `video`. The catalog checks every entry against the declared type —
inside the root, present, admitted by extension, meeting its `Metadata` — and
refuses the corpus whole, listing every shortfall, before anything is written.

Three packages share the work. `strata-contracts`, renamed from
`strata-labels`, defines what crosses: the sample types, their `Metadata`, the
prepared index and a pure check of an index against a type, beside the values,
schemas and manifest it already held. `strata-prepare` turns raw data into a
prepared corpus: the preparer framework, the folder preparers, and the
conformance suite. The catalog stores: it reads the index, runs the check, and
decides the bytes. Neither of the last two imports the other.

## Why the index is the only way in

Ingest used to walk a directory, keep what a type's extensions admitted, and
ask the type what to record about each file, which read the index if one was
there and guessed if not: a frame's video was its directory. A corpus nobody
prepared ingested anyway, a frame with no video became a group of one, and a
split frozen with `group_by = "video"` put its neighbours on the other side
without anything saying so. Declaring the corpus moves every such guess to the
one place that knows the answer, and lets the catalog refuse what is missing
instead of filling it in. A directory that is already in shape is declared
where it sits: a folder preparer run over the data root indexes the files in
place.

## Why a type's metadata is a model

Required keys are a fact about the data, like the extensions: a frame is a
frame of some video. Written as a model, the requirement is checked the same
way by the preparer's own tests and by the catalog, and a subtype can only
extend it, so where a `Frames` is accepted a subtype of it still carries
`video`. Keys a type does not declare are kept, since a preparer records what
it knows and a key becomes required only when a type says so.

## Why the types left the catalog

A preparer has to know what it is producing and what that requires, and it
should not need a database driver to find out. With the types in the catalog,
every preparer depended on SQLAlchemy and alembic for a class with an extension
list. In `strata-contracts` they sit beside the manifest, the matching contract
for what leaves a catalog (record 0004), and the registry resolves through
`strata-common`, which is the one dependency `strata-contracts` gains.

## Canonical form stays with the bytes

A catalog decides what a checksum addresses, so canonical form is the
catalog's: per media, with text stored as UTF-8, LF, NFC and no BOM (record
0010), and a plugin type registering its own under `strata.canonical_forms`.
A candidate annotation, though, addresses the bytes a preparer wrote, so a
preparer that ships spans over text writes that text canonical itself, and a
catalog refuses a candidate riding on bytes it would rewrite rather than land
offsets that point at other characters. That refusal is also what catches a
preparer's rule and the catalog's drifting apart. A preparer carrying no
annotation owes no canonical form; the catalog applies it.

## What this replaces

This supersedes record 0010's placement of sample types in the catalog, and its
statement that a type owns what is recorded about each file and the form its
bytes are stored in: a preparer records it, a type says what it must include,
and canonical form is the catalog's, set per media rather than by the type. It
supersedes record 0023's directory as the grouping of last resort: the
`frames-folder` preparer states it as a fact, and a frame directly in the root
is refused. It supersedes two of record 0033's preparer promises: a corrupt
index no longer leaves a corpus to ingest, since the index is what is ingested,
and a preparer's output need not be canonical unless an annotation rides on
it. Record 0033's suite gains the check a catalog runs.

## Consequences

- An index is version 2, required, and names its type. A version 1 index,
  written before, is refused by both packages with the instruction to prepare
  again; plant's 54,305-entry corpus is one.
- Every project runs `prepare` before `ingest`, including one whose files are
  already in shape, where it writes only the index.
- A corpus with one bad file ingests none; the refusal lists what to fix, and
  the re-run is the one that counts.
- `strata-catalog preparers` became `strata-prepare preparers`, and
  `strata-catalog types` now says what each type requires and whether it is
  stored canonical.
