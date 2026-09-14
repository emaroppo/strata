# 24. A version says where its sides began, and records the split it was given

**Status:** accepted

## The decision

Record 0003 says a version's sides are inherited. This records how a lineage
begins and ends, and what a split the corpus arrived with means.

A version inherits its sides from the previous version of the same name unless
`inherit=False`, which re-splits and starts a lineage of its own; every
version records the version its sides began at, and a warm start never reaches
past it. A seed is part of a re-split's identity and not of an inheriting
version's. A given split, read off a metadata key the corpus arrived with, is
recorded as the freeze read it, and a given side contradicting an inherited one
is refused.

A split the corpus arrived with is reproduced, not corrected. Given sides are
fixed first and win over grouping; a group the benchmark cuts across sides is
reproduced and the cuts are counted as `groups_cut`; a given side counts toward
the drawn ratio, so a benchmark's test set is the holdout and nothing more is
drawn for it. Two freezes given different splits are two versions.

## Why a lineage has a beginning

A run warm-starts from the previous run over the dataset. A run that trained
before a re-split may have seen what is now held out, so continuing it would
leak. The version records where its sides began, the run store will not
continue past that point, and a version with no recorded origin starts a
lineage of its own rather than claiming one.

## Why a given side wins

Public corpora come pre-split, and a result is comparable to published ones
only if the version holds out exactly the published test set. Correcting the
benchmark's division for a grouping it did not respect would make the number
mean something else. So the cut is reproduced and counted, and the count is
there to be read beside the number. This replaces 0003's consequence that a
straddling group is forced to train: that is the rule for groups the draw
decides, not for sides the corpus decided.

## Why a given side is refused against an inherited one

A version that inherits sides and is also handed a given split may be told to
put a sample on a different side from the one its lineage put it on. Honouring
the given side would move a sample a warm-started model has already seen into
validation. It is refused with the count, and `inherit=False` is how to say the
lineage should end here.

## How the draw fills

Holdout is drawn first so validation comes from what it left; holdout is
forced only with three or more groups, since with two a forced holdout would
trip the refusal of a one-sided split. Fill aims at the deficit rather than
flipping a coin per group, so an earlier version's off-target ratio is
corrected; overshoot is capped at half a group, and the fallback takes the
closest group when nothing improves, because too large is usable and empty is
not. Achieved ratios are recorded beside the asked-for ones.

## Consequences

- Identical means the same members, answers, ratios, grouping and given split;
  a re-split must also match the seed. A null digest is unknown, not equal,
  which costs one visible extra version per project on upgrade rather than
  silent staleness.
- A dataset is bound to one label set, or materialising would have to be told
  which.
- A seedless split stage reads the version's sides so trials are comparable; a
  seeded one draws into a copy named for the draw and never rewrites the
  version. The same `apply_sides` writes the directory for the split stage and
  for the modelling host, so both write the same thing.
- An experiment uses the project's grouping unless the file says otherwise,
  including none: a study may split what the project keeps together.
