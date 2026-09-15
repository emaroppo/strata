# 11. A feature is a role, not a fact about the data

**Status:** accepted

## The decision

A target is what a model is asked for; a feature is something already
known that it may be told. A project declares its features by naming
where to read each value — another label set's answer, or a metadata key
on the sample — and the same place can be a target somewhere else. A
feature must be present for every sample the project draws from. In the
manifest and the model contract, features are plain JSON, positional
against the paths.

## Why role is per job

The same annotation is the target of the project that owns it and a
feature of another, at the same time, over one catalog. Nothing about the
stored answer differs; only the declaration in the project that reads it.
That is what makes a catalog's annotations compound rather than
accumulate: what one round acquires is what a later project is told.

## Why two sources, named explicitly

`label_set` is the primary case. `metadata` is for values with no label
shape — coordinates, a capture time, a frame's index — where there is no
class list to declare and no reviewer who could have supplied one. A bare
name would have to guess between the two, and guessing wrong reads a
different value.

## Why coverage is a precondition, counted

`push` scores the whole unreviewed pool to rank it. A sample whose feature
is missing cannot be scored, and a queue that only ever surfaces covered
samples never gets the rest labelled — a bias nobody chose. So the rule
is checked and counted rather than inferred from where the value came
from, and a missing value is reported rather than filled in: a zero is an
answer and "not known" is not.

## Why plain JSON rather than a label value

The `AnyValue` union is choices, spans and boxes. A coordinate pair is
none of them, and a feature read from a metadata key has no label shape
at all. Typing features as label values would make the label-set source
the only one expressible, which is the corner worth not painting into.

## Consequences

- Features are resolved where the catalog is, at materialise time, because
  a materialised directory has to be readable without one (record 0004).
  Only declarations cross the wire; the host reads the values from its own
  catalog.
- A feature's value goes into the prediction cache's key (record 0006).
- `predict` takes features keyword-only, because the argument arrived after
  the callback and inserting it before would silently rebind every
  positional call.
- A model declares the features it needs, and training refuses a dataset
  that does not carry them before the round, not during it — a model that
  needs a feature nobody supplies would train on whatever a missing value
  degrades to, silently, and report a number for it.
- `requires_features` means cannot predict without, not cannot train
  without. A model that learns to infer a feature as an auxiliary task
  wants it while training and never at inference, and declaring the
  stronger thing would make that model inexpressible.
- A feature's name is what the model calls it, distinct from its ref,
  because what a model wants is not always named the way the catalog
  stores it.
- A version's manifest records the declarations it was built under, so a
  materialised directory still says where its features came from once it
  is somewhere else. Only the name is contract, since it is what
  `requires_features` is checked against; source and ref are the catalog's
  own account.
- A member whose feature is under dispute is left out of the materialised
  version and named in the manifest: two people answered the label set it
  reads from differently, and neither answer can be told to a model as a
  fact. It is back once someone settles it.
