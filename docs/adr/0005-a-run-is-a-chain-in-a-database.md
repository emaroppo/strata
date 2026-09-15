# 5. A run is a chain in a database, with an id that needs no coordination

**Status:** accepted

## The decision

Runs, their metrics and their predictions are rows in a run store, one
per project and one per modelling host, always SQLite. A run names its
parent, the dataset version and model version behind it, and the class
list as trained. Its id is a timestamp with microseconds and a host token.
Metrics are rows, one per name, with the training curve as further rows
keyed by epoch. Two stores merge by copying what the target lacks.

## Why a database rather than a folder of JSON

Runs are a **chain**: each round warm-starts from the last, so a run's
metrics only mean something relative to its parent, and telling a real
improvement from a warm start's head start needs the edge, not just the
node. And "accuracy per round" is the single most useful question to ask
of a history; it should be a query rather than a glob and a parse.

## Why the id is a timestamp and a host

Unique without asking anyone, which is what lets a laptop train offline
and fold its history into the main store afterwards. Two machines cannot
collide because the host differs; one machine cannot collide with itself
because training takes minutes and the timestamp carries microseconds.
Legible on purpose: a random suffix would be unique too and would say
nothing, while the two facts worth knowing about a run months later are
when it happened and which machine did it.

Run ids used to autoincrement, which meant something only inside one
store — and there were two, both numbering from one. There was no
migration; a store from before was refused with a message while any
existed, and the refusal went once none did.

## Why the class list is on the run

Checkpoints map output neurons to classes by position. A warm start from
a checkpoint whose class list has since been reordered corrupts silently
rather than failing, so classes are append-only and the list as trained
is recorded and checked. When the list only grew, the text heads rebuild
the head and keep the encoder's fine-tuned weights; a list changed any
other way starts from the pretrained encoder.

## What a checkpoint holds

Tensors and plain values: a state dict, the class list, and for the text
baselines the name of the encoder. Nothing in it needs an unpickler, and
both baselines load with `weights_only=True`. The text loader shipped
with it off from the day it was written, for no reason the history
records, and stayed that way through two refactors while every checkpoint
on disk loaded fine with it on. A checkpoint is the one artefact that
arrives from another machine — a merge copies them on request — and a
loader that will execute what it is handed turns every copied run into a
code path. Anything a checkpoint needs beyond tensors and plain values is
a change to this record, not to the flag.

## What else a run records, and why

- **The model's version.** A model is upgraded underneath a project, and
  its version is bumped when a change makes old checkpoints unreadable. A
  warm start across a version is refused: output neurons map to the class
  list by position, so a mismatch corrupts rather than fails.
- **The model reference, anchored.** Predicting or warm-starting from a run
  later must not depend on the directory a file reference was relative to
  still being there.
- **The catalog, from the manifest.** Not from the request: the directory
  is the record of what was trained on, and the one thing the local and
  remote paths share.
- **The experiment that asked for it,** so a study is a query over the
  store rather than a walk of the ledger.
- **What it saw.** The side of every sample in its manifest, the split as
  realised, inherited or drawn, so it is asked of the run rather than of a
  directory that may since have been deleted. A run from before this has no
  rows, which means unknown, not empty.
- **The machine, by name.** The id carries a host token for uniqueness;
  the name is stored too because an id is immutable and a machine can be
  renamed or handed on.
- **The curve, kept by the handler** as well as forwarded to the caller. A
  model that never calls back records none, which is the honest answer
  rather than a fabricated one.

Adding a class should not cost the rounds already trained. An image head
grows: new neurons start from a fresh init while every existing class keeps
the row it learned; any other change to the list shifts the index each
neuron stands for, so the model is rebuilt. A checkpoint's saved
configuration is provenance only: hyperparameters belong to
`[model.params]`, and letting a checkpoint override them made editing them
look like it did nothing. The label set's class list is append-only by
convention rather than by constraint, because a run records the list it
trained with, and that, not the catalog's row, is what a checkpoint is
checked against.

History and the latest run are ordered by creation time, the id breaking a
tie, because a store can hold ids minted elsewhere. A merge copies metrics
without their ids, since a metric's id is its store's numbering and the
target mints its own. A run's short form drops the microseconds for people;
the full id is what everything keys on and what a merge needs.

## Consequences

- A run is written only once it finished; a round that died halfway
  leaves no run and no curve. The curve is written with the run because
  the metric rows point at it.
- The curve is read separately from the run, because every caller wants
  the final numbers and only a chart wants epochs times metrics.
- Merging copies oldest first so a parent is in place before the run that
  continues it. A parent in neither store cannot be honoured: the link is
  dropped and the run reported, because a dangling parent would make the
  history claim a lineage it cannot show.
- What a run saw is recorded per sample with the side it was on, which
  import batch its label arrived in and whether a person vouched for it,
  as the manifest said. So a run can answer, per side and per batch, how
  much of what it learned from nobody checked, and `report` shows the
  validation share beside the metric: a validation set of unreviewed
  imports measures agreement with whoever labelled them. Null means the
  manifest did not say, which is not the same as unreviewed.
- Checkpoints are left behind by a merge unless asked for. They are the
  large half by orders of magnitude, and a run whose checkpoint did not
  come has its column cleared rather than left pointing at a file on
  another machine.
