# 28. An import is trusted until a person looks, and the look is a named batch's spot check

**Status:** accepted

## The decision

Labels that arrive with a corpus land at ingest, under `source=import` and a
batch name that is required before anything is written. They are trusted and
trained on, and recorded as unreviewed. A review of an import is a spot check:
`push --review-imports` ranks the queue by the model's disagreement with the
import, not by uncertainty, and leaves disputes out. The reviewer sees the
imported label and confirms or corrects it. An export takes only what a person
touched when asked to, and an audit is a blind second look. `report` shows, per
batch, how many imports were accepted, corrected and are pending, and beside
each run's metric how much of its validation set nobody checked.

## Why trusted, and why recorded

A corpus that arrives labelled is the most common way to start, and refusing to
train on it until every label is checked would mean never starting. Trusting it
silently would mean a result nobody can read against the labels it rests on.
So the labels are used, and every one carries the fact that no person vouched
for it, until one does.

## Why the batch name is required

Unnamed labels have nothing to be reviewed by and nothing to be reported by.
Requiring the name before the first write costs one argument; inventing one
would make every later question about the import unanswerable.

## Why candidates, and why a separate step

Labels a preparer carries out of a corpus are candidates, never truth: a regex
found them, or someone's model. They travel in the prepared index and land in
a separate step under their own source, so an export cannot mistake them for a
person's answer.

## Why disagreement, and why disputes stay out

Imports are trusted, so the ones worth a person's hour are those the model
disagrees with most: one minus the model's mean confidence in the classes the
import asserts, with a class the model never named counting as zero. A dispute
is two people disagreeing, and this queue is one person and a corpus.

## Why the export is careful

Label Studio stamps every export human. A seeded task arrives answered, and a
partial export would write guesses back as ground truth. A person's presence on
a task is read from `lead_time`, a draft or `updated_by`, since an unopened
import carries none, and `--reviewed-only` takes those alone.

## Why the audit is blind

An audit draws from the answers that accepted a pre-annotation, the only ones
it can say anything about, and clears the model's answer from the task first,
so the reviewer's answer is the first opinion again rather than a nod.

## Consequences

- A validation set of unreviewed imports measures agreement with whoever
  labelled it, not accuracy, which is why the share is beside the metric.
- Second looks, an audit's or a correction somebody came back for, are counted
  as agreed or changed.
