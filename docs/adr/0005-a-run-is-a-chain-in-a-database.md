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
store — and there were two, both numbering from one. There is no
migration: an id minted this way and an integer sort against each other
by first digit, so a store from before is refused with a message rather
than failing on a missing column later.

## Why the class list is on the run

Checkpoints map output neurons to classes by position. A warm start from
a checkpoint whose class list has since been reordered corrupts silently
rather than failing, so classes are append-only and the list as trained
is recorded and checked.

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
- Checkpoints are left behind by a merge unless asked for. They are the
  large half by orders of magnitude, and a run whose checkpoint did not
  come has its column cleared rather than left pointing at a file on
  another machine.
