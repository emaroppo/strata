# 33. A plugin's promise is an executable suite it runs itself: models, preparers, sample types

**Status:** accepted

## The decision

The registry proves that a plugin imports and nothing more. What a plugin
promises is a conformance suite it runs against its own work, shipped behind
the test extra because it imports pytest. Models, preparers and sample types
each have one. Built-in kinds are deliberately few and live in the same
registry, so `available()` gives one answer; a name registered twice is
refused rather than resolved by install order.

## Why executable

A model that accepts the wrong callback fails on the first epoch of a real
round. A preparer is the one place bytes are invented, and a mistake there is
unrecoverable once a corpus is annotated. A written contract is read once; a
suite is run on every change, by the plugin's own tests, without the plugin
depending on anything but the package that defines the contract.

## What a preparer promises

Its output is admitted by the type it declares, or the corpus ingests empty and
is misreported as being in the wrong place. Its output is canonical by
construction, so the file on disk and the catalogued sample share a checksum.
It is deterministic: a re-run produces the same bytes at the same paths, or the
corpus re-checksums and every annotation is orphaned. An unreadable source is
refused, not skipped. The index it writes is merged with what is there, so
converting a grown source adds rather than forgets, and a corrupt index does
not refuse a corpus, since the files are what is ingested. A preparer is
resolved from the type it produces and the extension it reads, with an
ambiguity refused by both names.

Two decisions the preparers make for themselves belong beside this. A prepared
file is named for what it says, not where it sat: positional names re-ingest
everything after an insert as new, unannotated samples, and a directory of
frames named by the video's own checksum keeps its frames' names. Mail is its
plain text part, and a message without one is refused rather than skipped:
offsets into HTML land in markup and a model learns tag names, and rendering
HTML is a conversion of its own. Spans a preparer carries out of a corpus are
candidates, remapped through the same transformation as the text and dropped
and counted when they no longer fit, since a nearly-right offset is worse than
a missing one. Every frame is decoded rather than sought, because seeking lands
on the nearest keyframe and is codec-dependent, and determinism is what keeps
a re-prepared corpus from re-checksumming.

## Consequences

- The mail preparer refuses a message longer than an arbitrary limit. That
  lets a number chosen at conversion decide what the durable asset holds, the
  reverse of the architecture's stance; it is a first-pass compromise with the
  source kept, and no condition for lifting it has been decided.
- The union of prediction types is not a plugin surface: a new label type goes
  into `labels` first, and every layer reads it through the union (record 0004).
