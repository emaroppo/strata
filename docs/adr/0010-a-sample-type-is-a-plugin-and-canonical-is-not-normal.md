# 10. A sample type is a plugin, and canonical form is not normalisation

**Status:** accepted

## The decision

What a sample *is* belongs to the catalog, as a plugin type registered
through an entry-point group and free to inherit. A type owns four things
at ingest: which files are admitted, what is recorded about each, how
samples group, and what canonical form their bytes are stored in. A
preparer is the companion surface: it converts a corpus into what a type
stores, writes files and an index of what it knew, and stops; `ingest`
catalogues. Built-in names are reserved.

## Why it belongs to the catalog

It is a fact about the data, not about the tool that collected it. When
the labelling tool held the extension list and the grouping rule, the tool
defined what a sample was and the catalog that stored it did not.

## Why inheritance is safe here and not for label sets

A label set's classes map to a checkpoint's output neurons by position, so
a parent gaining a class silently reindexes its children; label sets are
copied. A type is code, and `Satellite(Image)` overriding one method has
nothing at a distance. Substitution has to hold in two places: in code it
is `issubclass`; in queries, where the database holds strings, the subtype
is a path matched by prefix, the same rule collections use. The stored
pair is a denormalisation of the class chain, and both are checked when a
type is defined. A subclass may not change its media, or a query for
images would quietly stop returning it.

## Why extensions are an allow list, checked and reported

Ingest walks what it is pointed at; a sensibly arranged folder is the
user's job. What it must never do is take in less than it was given
without saying so — files outside the list are skipped *and counted*, and
a walk that matches nothing is an error. Filtering silently is how a
corpus ends up quietly smaller than the directory it came from.

## Canonical form, and the line it does not cross

A line ending or a byte order mark is not a difference between two
documents, but it is a difference between two checksums — and for
anything annotated by character offset, a difference between two sets of
offsets. A browser normalises line endings on its own, so a document with
CRLF hands a reviewer different offsets from the ones a tokenizer sees,
and nothing raises. Measured on one prepared corpus, 3% of documents
carried CRLF and a 144-document slice put 19 spans on the wrong
characters. So text is stored one way: UTF-8, LF, NFC, no BOM. Encoding is
refused rather than guessed, because a mojibake document ingests, renders
plausibly, and is annotated against characters that were never there.
Converting an encoding is a preparer's job, since only it knows what the
corpus is.

The line is whether two independent implementations would produce
identical bytes. Consistent column names, key ordering, whitespace someone
prefers — anything that encodes a preference — would make a checksum
depend on our own release, and merging matches samples on checksum
precisely so that two hosts on different releases agree about what a
sample is. Images have no canonical form, and ingest reads no file for a
type that declares none, so a corpus is still linked rather than copied.
A type's canonical form is handed to ingest by its caller rather than
resolved by the catalog, so a catalog stays free of the type registry.

## Why preparers are upstream of ingest, and their own distributions

Keeping conversion and cataloguing apart is what stops a converter
becoming a second implementation of content addressing, grouping and
collections. A converter carries a decoder or a parser that most installs
have no use for, so each ships as its own distribution and the catalog
never imports one. What a preparer knew — which video a frame came from,
who sent a message — travels in one index at the corpus root rather than a
sidecar per file, and grouping becomes a declared fact rather than a
directory convention two pieces of code have to agree about. Determinism
is the promise that matters: a conversion that produces different bytes on
a second run re-checksums the corpus, and re-checksumming an annotated
corpus does not lose the annotations — it detaches them. A project keeps
the corpus as it came under `source_root`, apart from `root`, which holds
it as the catalog stores it.

## Consequences

- Mail is stored as message bodies, with headers as metadata: anything
  prepended to a body shifts every offset annotated against it. Headers
  are chosen rather than kept wholesale, since a header block runs to
  dozens of routing lines nobody will query and metadata is stored per
  sample. `Message-ID` is recorded as the join key: the same mail ingested
  in a second format is different bytes and so different samples, and the
  id is what would carry the review work across.
- The video preparer still writes a directory per video beside the
  declared grouping, so the corpus stays browsable and a corpus laid out by
  something else still ingests. It admits containers, not codecs: what
  OpenCV can decode depends on how it was built, and a file it cannot read
  is reported rather than skipped.
- Message threads are not yet grouped. Near-duplicates on both sides of a
  split are the same problem as video frames; deciding which messages are
  one thread is a decision about a corpus, not about mail.
- A canonicalised file records the original's checksum, so a sample can
  still be traced to the file on disk it came from.
- A project declares its media and subtype because ingest needs them
  before anything is catalogued; afterwards the samples are the truth. A
  collection holding other media or subtypes is warned about rather than
  refused, because one catalog holding standalone images and video frames
  at once was the point of recording grouping per sample.
