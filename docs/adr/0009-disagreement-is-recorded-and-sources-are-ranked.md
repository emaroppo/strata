# 9. Disagreement is recorded, sources are ranked, and unlabelled is the absence of a row

**Status:** accepted

## The decision

An annotation row exists because somebody dealt with the sample; its
state says how. Unlabelled is the absence of a row. Every answer carries
its source — human, import, model — and sources are ranked: a person
outranks an import outranks a model, and a write never replaces an answer
from a source that outranks it. When a merge finds two answers of equal
standing that differ, the target keeps its own and the disagreement is
recorded beside it. Returning a sample to the queue supersedes its row;
the history is kept (record 0027).

## Why unlabelled is the absence of a row

There is then no combination of flags that means nothing. A reviewer who
looked and found none of the classes present has *answered* — an empty
value is a real annotation, distinct from a sample nobody has seen. The
queue is defined by the absence of a current row. `unskip` and `discard`
stamp the row superseded rather than flag it, which returns the sample to
exactly the state an unreviewed import starts in while the record of the
skip stays (record 0027).

## Why sources are ranked

Re-running an import after a review pass must not quietly undo the
review. Labels that arrived with a corpus are trusted over a model's guess
and never over a person's. A person's answer arriving where the target
holds an import replaces it, or confirms it if they agree; an import
arriving where a person answered is left out. Neither is a disagreement
between two people, so neither is put in front of one.

## Why a merge records rather than resolves

Both answers were made by a person looking at the sample, and a merge is
not in a position to decide which was right. It keeps one, remembers the
other, and puts the pair in front of a human: `push` sends disputed
samples to the front of the queue, ahead of the uncertainty ranking,
because where they would land there depends on the model's opinion, which
has no bearing on two people disagreeing. Answering again clears it,
whichever way they go. One row per sample per label set: the pair being
shown matters more than the history of who disagreed when.

The conflict is recorded beside the one current answer, not in place of
it: everything that reads an annotation wants the answer, not a set of
candidates. It names the catalog the other answer came from, so "the
laptop said otherwise" is answerable rather than merely "something did".

## How a merge ranks what arrives

An answer beats a skip, since someone got further with the sample than
someone else did, unless the skip was a person's and the answer an
import's: then nobody got further and a guess arrived. Each answer travels
with its source. Left behind, every arriving answer would be written as a
person's, and an import made on a laptop would come home looking reviewed.
A label set the target has never heard of is reported, not created: it is
far more likely a typo or the wrong copy than something the target wants
invented on its behalf. A dry run reads everything and writes nothing, so
the report can be shown before anything is committed; a conflict is the
interesting outcome, and fifty of them are easier to look at before the
merge than to find afterwards.

## Consequences

- Only annotations move in a merge. Samples do not, and that is a limit
  rather than an oversight: a merge that ingested as well as annotated
  would have to decide what a corpus is made of.
- A partial import is worse than none: a document annotated only in part
  reads every unmarked class as a deliberate negative. `discard` is scoped
  by source, and the source has to be named, so an answer a person gave is
  never removed by a call that meant something else.
- Values forbid unknown fields, because an empty value is an answer here:
  a typo would land in the catalog as "nothing present" and read back as
  one.
- Two people labelling the same sample on two machines is last-write-wins
  until their answers meet in a merge. Adequate for one person; a real gap
  the day it is two.
