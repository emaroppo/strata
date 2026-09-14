# 35. Evaluation is one implementation, and a model's own numbers are its own

**Status:** accepted

## The decision

The `evaluate` stage scores a run by one implementation, on the held-out side,
from what `predict` returns. What a model reports while training is recorded
as its own number and never mistaken for a score. A delta between runs is
measured only along a chain, against the run's own parent, on the same held-out
samples. Classification is scored as exact match plus micro precision, recall
and F1; spans are scored one entity per label with one-to-one matching, as
exact and partial F1 per class; boxes are refused for now.

## Why one implementation

Two runs are comparable only if the same code scored them. A model's training
loop reports whatever it likes, on whatever it saw, and that number is useful
to the model's author and to nobody else's comparison. Scoring from `predict`
scores what reaches the cache, Label Studio and the reviewer, which is the
thing a number should be about.

## Why these metrics

Exact match and micro PRF are neither called accuracy: a label set with two
classes per sample scored by a model asserting one has an exact match of zero,
and calling that accuracy would be wrong in the direction that flatters. A set
score over spans or boxes would be a number, and not the one anybody means by
it, so it is refused rather than approximated. For spans, one-to-one matching
is what stops a sentence-wide span scoring perfectly against every entity in
it; exact and partial are both reported because one understates and the other
flatters, and per class because entity types are uneven.

## Why the delta rule

A warm-started number means something against its parent and nothing against
a run from another lineage. A dataset version going backwards means the lineage
crossed in from the old layout, where the split was recomputed every round, and
comparing those measured only a change of validation set. None is "cannot be
compared", which is not "did not move". The JSON carries `params` and `classes`
because those decide whether two runs are asking the same question at all.

## Consequences

- The headline metric is per task; a span project defaulting to
  `val_accuracy` reported nothing for every run.
- Span-level and box-level scoring in the stage are on the roadmap; until
  then the taggers score their own spans, from `predict`, and say so.
