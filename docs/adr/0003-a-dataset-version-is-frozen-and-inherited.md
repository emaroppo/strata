# 3. A dataset version is frozen, its sides inherited, its identity its answers

**Status:** accepted

## The decision

A dataset is a saved selection, written down as rows, not a query
re-evaluated at training time. Each version assigns every sample a side —
`train`, `val` or `holdout` — and the next version inherits every side its
predecessor decided, assigning only what is new. A version's identity is
its members *and* a digest over their annotations. Groups are indivisible.
A holdout is drawn first, then validation from what it left.

## Why membership is written and inherited

Rounds warm-start from the previous checkpoint. A sample that migrates
into validation between rounds is scored by a model that has already
trained on it, and the number comes out flattering. Recomputing the split
each round did exactly that. Written down and inherited, a warm-started
model is never scored on what an earlier round trained it on.

## Why identity includes the answers

Membership alone was the whole test until a correction was shown to leave
it unchanged: correcting a label leaves the sample set identical, so the
round after a correction was handed the previous version, skipped
materialising because its manifest was already on disk, and trained on the
values the correction had replaced. The digest covers state, source and
value, because a reviewer changing one class to another and a reviewer
confirming an imported guess are both changes a frozen version must not
pretend it already holds. A digest rather than a timestamp watermark,
because `updated_at` is second-resolution: one bulk write lands thousands
of rows in one second, and a correction inside it moves no watermark.

## Why three named sides rather than a flag

A flag has no room for a third. A held-out sample that a reader took for
"not validation" would be trained on — silently, and on exactly the
samples kept back to be measured on honestly. `holdout` never reaches a
model, in training or in validation; it is what a study that selects on
validation is measured on afterwards.

## Why groups are indivisible, and what that costs

Near-duplicates on both sides of a split make a validation score
meaningless, so frames of one video move together. A standalone sample is
a group of one, so the same code serves both and one catalog holds both.
The cost is that a ratio can be unreachable — two videos cannot hold out
20% of themselves — so the achieved ratio is returned and recorded rather
than assumed, and a caller who asked for 20% can find out it got 50%.

## Consequences

- A retried round reuses its version: a version describes a selection, not
  an attempt at one. But a version asked for with a different holdout ratio
  is a new version, however identical its members.
- Inherited sides are never overruled, so a version whose every sample an
  earlier version placed draws no holdout, and says so. A study wanting one
  there draws its own split and records the draw (`orchestrator.md`).
- A group straddling sides that the draw decides is forced to train, which
  removes the leak rather than preserving it. A cut the corpus's own split
  made is reproduced and counted instead, since a benchmark's division is
  what a result is compared against (record 0024, which also records where a
  lineage begins and ends).
- The materialised directory is self-contained (record 0004), so a run
  resolves back to the exact samples and answers behind it by version.
