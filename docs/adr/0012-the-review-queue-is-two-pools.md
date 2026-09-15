# 12. The review queue is two pools, and the unscored are left out

**Status:** accepted

## The decision

A review queue is ordered by an active-learning strategy over each
prediction's confidences. Samples the model found nothing in are drawn as
a separate pool, in a declared proportion of the batch, and the proportion
holds at every prefix of the queue. A sample nobody scored is left out.
Strategies live with the labeller, not with the value types.

## Why two pools

"Correct what I found" and "confirm there is nothing here" are different
requests, and every strategy scores an empty prediction at exactly 1.0 —
so empty predictions arrive as a block of ties at the front and monopolise
the queue rather than competing for it. Measured on one span project: 684
documents the model found nothing in took the whole of a fifty-task batch,
while 12,333 documents with real predictions to correct sat unreachable
behind them, and every one of the fifty was a message of a few dozen
characters that genuinely contained nothing. Drawn as two pools, both
still ordered by the strategy, neither can crowd the other out. The
proportion holds at every prefix so that a caller taking the top N gets
the same mix as one taking all of it.

This never bit classification, because a classifier cannot return an
empty prediction — the image baseline falls back to its best guess when
nothing clears the threshold. The rule was written for a case that could
not arise until a task could honestly assert nothing.

## Why the unscored are left out

A sample nobody scored placed in a queue that claims to be
least-confident-first would be a fiction. It is still unlabelled, so it
comes back next time.

## Why a density strategy exists, and when to stop using it

Uncertainty answers "what would teach the model most per document".
Early on, "where is a reviewer's hour worth most" is a different question.
For spans, uncertainty avoids dense predictions structurally: a document
scores as its *least* certain span, so one carrying fifty almost surely
holds a weak one. On one project the pool averaged 22 predicted spans a
document while an uncertainty-ranked batch averaged under one, and
reviewing the sparse ones yielded a tenth of the training signal per hour.

Counting every span was the wrong measure, and the first version did: it
selected the documents the model was most wrong about — the densest had
400 spans in 3,896 characters, most of them noise — and deleting a wrong
span costs what marking a missing one does. Counting spans over a
confidence threshold separates the two and stops rewarding a model for
guessing more. The threshold is 0.9: a span the model is that sure of is
usually right enough to confirm at a glance, and below it checking costs
about what marking from scratch does. A model that asserts spans and says
nothing about how sure it is has every span counted: absent is unknown,
not unconfident, and scoring it zero would hide such a model's output from
this ranking entirely. Right while a training set is being built, wrong once it
exists: a model already good at these documents learns nothing from
another. Name it deliberately, and stop naming it when that turns.

## Consequences

- The number shown beside a pre-annotation is the inverse of the default
  strategy, so the score on a task and the order it arrives in cannot tell
  different stories.
- Which strategy to use is a choice about how to spend review time, not a
  fact about what a prediction is, so the strategies are the labeller's
  and a prediction carries only its confidences.
- Three producers of predictions — a cache, a local handler, a remote host
  — hand the ranking the same values, and nothing in the ranking can tell
  whether they agree. The value types are what make them.
