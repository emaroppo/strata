# 25. A round carries its split as a realisation, never its seed, and continues a parent only by a policy the caller states

**Status:** accepted

## The decision

A round sent to the modelling host carries the split as the caller's directory
has it: one letter per sample, positionally, with a digest over the order. The
host proves the count and the order first, then applies the caller's sides to a
copy of the version through the same split code the caller used, never
substituting the version's own sides. The protocol moved to 2 for this field,
because a version 1 host would silently ignore it.

Which run a round continues is a policy the caller states: cold, a named
parent, or the newest run over the dataset that is not past the last re-split.
"Fresh" is a request and "cold" is an outcome, so `fresh_params` apply only
when the round is actually cold, and both parameter sets travel because only
the host knows whether a parent exists there.

## Why the realisation and not the seed

A seed reproduces a draw only under the same code, the same grouping and the
same members. The letters are kilobytes, not megabytes, and are safe only
beside the order digest, which proves the reader holds the same samples in the
same order before anything positional is applied. Sent this way, the host
trains on exactly the sides the caller's directory has, whether inherited or
drawn, and a drawn holdout is scored as one.

## Why the parent is a stated policy

Warm-starting from "the latest run" was a hidden default, and it was wrong in
two ways: it would continue a run from before a re-split, which may have seen
what is now held out; and it made a grid's results depend on the order trials
ran. So the default is written down and the run store refuses to reach past the
last re-split. The same model is matched by its class name rather than its
reference or object identity, with modules keyed on the whole path so two
like-named `model.py` files do not shadow each other; a parent that cannot be
resolved is tolerated and reported rather than invented.

## Why a cold round has parameters of its own

A run with nothing to inherit learns from scratch, where a warm one is an
increment onto something already trained. The epoch count that suits one
undertrains the other, and a cold start on an increment's schedule reads as a
baseline when it is not one.

## Consequences

- A grid runs every trial cold or from one named parent (record 0037).
- `run_sample` records the split as the round realised it, inherited and drawn
  reading the same (record 0005).
