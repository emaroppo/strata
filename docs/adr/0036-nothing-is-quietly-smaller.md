# 36. Nothing is quietly smaller: what a step leaves out is counted and said

**Status:** accepted

## The decision

Wherever data narrows, what was left out is counted and reported, never
dropped in silence. Record 0010 states this for ingest. It holds at every
step: a preparer counts the sources it could not read; windowing counts the
targets it loses when a span cuts a token or an entity exceeds the overlap; a
"none of these" answer is counted rather than encoded; a class the model will
not learn is recorded on the run; the corpus scanner returns what it skipped at
each step.

## Why

A corpus that trains on less than it holds fails silently, and the failure
shows up as a metric that moved for no visible reason. Filtering on the way in
is the usual cause. So a step returns its omissions with its result, and the
command prints them (record 0030), and a count the reader can see beside the
number is what makes the number readable.

## The cases that argued it

- A span that cut a token used to supervise nothing; overlap is now enough to
  supervise, and a span that still does not align is counted as supervision
  that never happened, so an inexact match shows as an exact-versus-partial gap
  rather than a bug.
- "None of these" encoded as class zero would teach the first class; it is
  counted instead.
- A class the model will not learn, because no target survived windowing, is
  otherwise indistinguishable from one never taught; it goes on the run as a
  diagnostic.
- The diagnostics are collected in the one pass that already tokenises, so
  counting costs nothing.

## Consequences

- Every count has a name in the record or the run's metrics, and `report`
  shows the ones a reader needs.
