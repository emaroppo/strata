# 27. An annotation keeps its history, and a batch follows its answer

**Status:** accepted

## The decision

Annotations are append-only. A write stamps the current row `superseded_at`
and adds a new one, so the catalog remembers. The current answer is the
unstamped row, and unlabelled is its absence. `unskip` stamps the skip as
superseded and keeps it; it does not delete. A write that names no batch
inherits the batch of the answer it replaces. Predictions are not annotations.

## Why the history

An annotation was a cell updated in place with no memory. Every question about
how a corpus was labelled, how many imports a person accepted, how many they
corrected, how often a second look changed an answer, needed a record that was
being overwritten. Review counts are now read from the history, which is what
the history is for. This supersedes record 0009's statement that `unskip` and
`discard` delete the row.

## Why a batch follows its answer

A label arrives in a named import batch. When a person confirms or corrects it,
their row still says which batch it came from, so a batch can be read against
its review, and a run can say how much of what it learned from each batch
anybody checked (record 0005).

## Why predictions stay out

A prediction is a model's guess about a sample; an annotation is what somebody
decided. An accepted imported guess is worth telling from a label typed from
scratch, which is why the source travels with the row and why the two tables
are separate.

## Consequences

- A conflict table holds one row per sample per label set, since every reader
  wants the answer and not the candidates; the third answer replaces the
  second.
- A skip parks a sample with no class yet, which is where to look for examples
  after adding one; a cancelled annotation in Label Studio reads as a skip.
