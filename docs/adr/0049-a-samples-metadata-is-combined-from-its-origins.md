# 49. A sample's metadata is combined from its origins, and a type computes what its bytes say

**Status:** proposed; amends record 0040

## The decision

A sample's metadata comes from two places.

- **Facts about the bytes** are computed by the sample type from the
  stored bytes, after the chain has run. They are the same for every
  origin by construction. For mail they are `characters`, `word_count`
  and `html_tags`.
- **Facts about an occurrence** are recorded by the stages that read it.
  For mail they are the headers. For a frame it is its index in the
  video. The video itself is the frame's origin (record 0045). Each
  origin row keeps the facts of its own occurrence, exactly as the
  stages recorded them.

The sample's metadata is the combination of the two. Each origin's
occurrence facts are added in the order the origins were recorded. A
key the sample already has keeps its first value. A type's `Metadata`
contract is checked against each origin's facts.

This is a stopgap, and the TODO says so. A more coherent rule for
origins that disagree is left for later.

## What this amends, and why

- **Record 0040 held a sample's metadata to its type's contract as one
  value, written once per ingest.** With origin rows (record 0045), one
  sample can have several occurrences. Enron files the same message
  under `inbox/` and `all_documents/`, and the two copies differ in
  their `X-Folder` header. A single value per sample would have to
  overwrite one occurrence with the other. That is the wholesale
  replacement on re-ingest that already loses provenance today. So the
  contract is checked against each origin's facts. Every occurrence
  must carry what the type requires of it. The sample's combined view
  is derived from the origins.
- **A type gains a duty: computing what its bytes say.** Record 0040's
  types declare extensions and a contract, and record 0010's own their
  canonical form. Facts that depend only on the bytes belong with the
  type for the same reason canonical form does. The catalog stores the
  bytes, so it can always compute them again, and two origins cannot
  disagree about them.

## Why the first value is kept, and nothing is intersected

Keeping only the keys every origin agrees on would let one bad copy
erase a header that every other copy carries. Keeping the first value
can only lose a later variant from the sample's view, and the origin row
still holds that variant. A bad copy can add keys the sample lacked. It
cannot remove any.

The cost is known. For Enron's duplicate files the second `X-Folder` is
missing from the sample's view. A consumer that needs exactly one value,
as SFT does for a message's subject, gets the first origin's value and
is not told that another origin disagreed. The TODO asks for a rule that
says so.

## Why the headers stay on the sample at all

They could live only on the origin rows. But SFT needs a message's
subject, and a freeze may need its sender. Both read the sample. A
lookup through the origins on every read would make the common case
pay for the rare one, where one body has several occurrences.

## Consequences

- **`origin` carries a metadata column.** The sample's `metadata` is
  computed from the origin rows and the type when an origin is
  recorded, and can be computed again at any time.
- **Re-ingesting a known sample no longer replaces its metadata.** It
  adds an origin. The TODO item about `samples.describe` replacing
  metadata wholesale is closed by this.
- **`SampleType` gains a method that computes facts from the bytes.**
  `Email` computes `characters`, `word_count` (whitespace-separated
  words, as phishnet counted them) and `html_tags`.
