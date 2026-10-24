# 50. A dataset version records the spec that selected it, and the spec can be run again

**Status:** proposed, revised as built (see Revisions); amends records
0003, 0022 and 0024, extends records 0022 and 0039

## The decision

A freeze is handed a selection spec: which sample types it draws, and
optionally from which collections; which label set it draws answers
from; and conditions on metadata and on labels. The version
records the spec's canonical content, its hash, and a watermark: how far
the catalog had got when the freeze read it. Running the spec again at
that watermark gives the same members.

The members are still written as rows (record 0003), and a round still
trains on those rows. The spec is what chose them. Running it again is a
check that they are what it chose, not where they come from.

A freeze with no spec does what a freeze does today: every sample in the
project's collections with a current answer in the label set. It is
recorded as the spec that says exactly that (the types those
collections hold, the collections, the label set), so every version has
one.

## What this amends, and why

- **Record 0003 called a dataset "a saved selection, written down as
  rows, not a query re-evaluated at training time".** That still holds
  at training time. What changes is that the selection behind the rows
  is now recorded, and it can be run again. A freeze has to leave out
  samples by a rule: a message with HTML in it, or one too long for a
  model's window (record 0045 moved that choice out of preparation). A
  version that cannot say which rule it applied does not say what it
  holds. The `query` column was meant for this, but nothing ever wrote
  it or read it.
- **Record 0022 required every sample query to name its collections.**
  A selection spec names its sample types instead, and its collections
  only if it wants them. The rule was made because a review queue once
  filled with another project's data, unnoticed. A spec's scope is
  written in the spec and recorded on the version, and the freeze counts
  its candidates by collection, so a selection wider than meant is
  visible. Other queries keep the rule.
- **Record 0024 defined an identical version by its members, answers,
  ratios, grouping and given split.** The spec's hash is added. Two
  specs that select the same members today are still two selections,
  and they will differ once more samples are labelled. A version reused
  for the other spec would record the wrong one.

## The spec

```toml
# specs/enron-sft.toml, in the project's repository
[select]
types       = ["email"]                  # required
collections = ["phishnet/enron/single"]  # optional; omitted means every one
label_set   = "emails"
sources     = ["human"]          # which answers count; omitted means any

[select.where]
all = [
  { key = "html_tags",  op = "==", value = 0 },
  { key = "word_count", op = "<=", value = 2000 },
  { not = { label_set = "qc", asserts = "reject" } },
]

[select.lists]
exclude = ["enron-near-duplicates@2"]
```

- **Types** are named as prepare specs name them (record 0046), and a
  type covers its subtypes: `text` selects mail too, since an email is a
  text (record 0010).
- **A metadata condition** is a key, an operator and a value. The
  operators are `==`, `!=`, `<`, `<=`, `>`, `>=`, `in` and `exists`.
  Values keep their type: `2000` is a number, and `<=` compares numbers.
- **A label condition** is a label set, a class it asserts, and
  optionally the sources that count.
- **Conditions group** with `all`, `any` and `not`, nested as deep as
  needed. Nothing else combines them.
- **A list** is included or excluded by name and version (below).

The spec is a file in the repository of whoever trains, as a prepare
spec is (record 0046). The catalog stores its canonical content, never
its path. The children of `all` and `any` are sorted before hashing, so
the same conditions in another order are the same spec.

## Why a selection names its sample types

What a condition can ask depends on the type: mail has `word_count`, a
frame has `frame_index`. Naming the types says which contracts the
conditions are checked against, before anything is read. A collection
says where a sample came from (record 0022), not what it is, and one
collection can hold several types.

Collections are optional because a type is already a scope. A study of
every message in a catalog should not have to list every collection
that holds mail. The cost is that it will include another project's mail
in the same catalog, which is what the count by collection is there to
show.

## Why the format names no key

The spec's format must not change for a new project. So it names no
metadata key of its own: a key is data in the spec. `html_tags` and
`word_count` are facts the email type computes (record 0049). A frame
project writes `frame_index`, and strata's code mentions neither.

A misspelt key is still caught, without strata knowing the key:

- **A key a named type declares** in its `Metadata` contract (record
  0040) is checked against the declared type, so comparing a number with
  a string is refused. Two named types that declare one key with
  different types are refused together.
- **A key no named type declares** is allowed. The contract keeps
  undeclared keys (record 0040), and a message's headers are never
  declared one by one. But a key that no candidate sample carries is
  refused, with the keys that do occur. `word_cuont` matches nothing, so
  it cannot pass silently.

A comparison on a sample that lacks the key is false. `exists` asks
whether the key is there. The freeze counts how many candidates lacked
each key it compared.

## Why a label condition asks only which classes are asserted

The catalog never reads an answer's payload to answer a query (record
0039). Each label type says which classes a value asserts, and the
catalog indexes that. So a condition can ask "asserts `reject` in `qc`"
of spans, choices or boxes alike, and the catalog learns no shape.

What a condition cannot ask is anything about the payload beyond its
classes, such as a span's length. That needs a second schema method that
returns facts about a value, indexed the same way. It is left for later
(TODO).

## Why a list, for everything else

Some selections are not conditions on one sample: removing
near-duplicates, choosing by a model's predictions, or a hand-picked set.
Those are made by a script, and the spec names their result.

A list is a set of checksums with a name and a version, stored in the
catalog. Storing a different set under the same name makes a new
version, and a version never changes. A spec names a list with its
version, so a list redefined later does not change what an earlier
version meant. This is the feature store's stored entity list, which a
composition names in the same way.

A list holds checksums, not sample ids, because ids mean nothing outside
their catalog (record 0008). `copy` and `merge` carry lists. A name and
version the target already holds with other contents is refused, as a
raw row is (record 0045).

## Why the members stay, and what running the spec again is for

The feature store's frozen version is its spec: a read resolves the spec
again, against a store whose every fact has a time. The catalog keeps
its members because inheritance works on members. A round warm-starts
from the samples the previous version placed (records 0003, 0024), and
that has to hold whatever happens to the spec.

So reproducibility rests on the rows, as before. Running the spec again
answers a different question: are these members exactly what this spec
selects? `strata-catalog dataset verify <name>@<version>` runs it at the
version's watermark and compares. This plays the part of the feature
store's test that its materialised form equals its query form.

## What the watermark needs

Running the spec again needs every input to have a history. Most do:

- **Samples** are appended with an id, and a removal is a tombstone with
  a time.
- **Answers** are appended with an id, and superseded rather than
  changed (record 0027).
- **Metadata** is combined from origin rows, which are appended (records
  0045, 0049), and from byte facts, which never change.

Two inputs do not have a history yet, and this record extends their
records:

- **The class index keeps only current answers.** Each write deletes a
  sample's classes and writes new ones. It is keyed by annotation row
  instead, so the classes of a superseded answer stay readable. This
  extends record 0039: the index is derived the same way, and kept for
  every row.
- **A sample's collections have no order.** A membership row gains an
  id, which the watermark covers, and a time, for reading. Collections
  are added and never replaced (record 0022), so the history is just the
  rows in id order.

The watermark is the highest id of each appended table, not a time.
Record 0003 turned down a time watermark because one bulk write lands
thousands of rows in a second. Ids do not tie.

Two events change a row in place rather than append one: a tombstone,
and a skip withdrawn without a new answer. Each also appends a row to an
event table, whose id the watermark covers like any other. Their times
stay, for reading; a replay goes by the event's id. Every change a
replay needs is then an appended row with an id.

## Why the freeze reads under a lock

An id below the watermark has to mean "visible to the freeze". On
Postgres it need not: an id is handed out when a row is inserted, not
when its transaction commits. A write that took id 100, and commits just
after a freeze that saw id 101, sits under the watermark although the
freeze never saw it. A replay would include it. Timestamps are no
better, since Postgres stamps a row with the time its transaction began.

So the freeze takes a lock, in its own transaction, on every table it
reads, before it reads. The lock waits for writes already in flight to
commit, and holds new ones back until the freeze commits. Nothing is in
flight when the watermark is taken, and every id under it was committed
before it.

SQLite already behaves this way: it has one writer at a time, and the
freeze opens its transaction as a writer. The lock makes Postgres do
what SQLite does, so a hosted catalog and a local one replay alike, and
the same tests hold for both (record 0021).

The cost is a pause. A Label Studio sync, an import or a judge run waits
for as long as a freeze reads, which is seconds for a corpus of tens of
thousands. A freeze that starts during a long import waits for the
import to finish. The locks are taken in one fixed order, so a freeze and
a writer wait for each other but never deadlock.

Versions frozen before this record have no spec. They keep their members
and cannot be verified, and `verify` says so.

## What a freeze counts

Nothing is quietly smaller (record 0036). A freeze records:

- the candidates: samples of the named types, in the named collections
  if any, with a current answer that counts, by collection and by type;
- the selected;
- for each condition directly under the top-level `all`, how many
  candidates it rejects by itself;
- for each key, how many candidates lacked it;
- for each list, how many members it added or removed.

## What this rules out

- **A query language.** There are no functions, no arithmetic, no joins
  and no expressions. The format is closed, and a new project needs a new
  spec file, never a new format.
- **Conditions on predictions in the spec.** Predictions live in
  modelling's run store, which the catalog never opens. They are left
  for later: the experiment layer would turn such a condition into a
  list, naming the runs it read (TODO).
- **A draw.** "A hundred of each class" chooses among what passes,
  which a condition cannot express. It is left for later (TODO).

## Consequences

- **A migration on both catalog databases:**
  - `dataset.query` becomes the spec, its hash and the watermark;
  - `annotation_class` gains the annotation row it was derived from;
  - `sample_collection` gains an id and a time;
  - lists get two tables, a list version and its members;
  - an event table records tombstones and withdrawn skips.

  The blob server images on minipc are rebuilt to the matching revision.
- **The dataset stage takes a spec** from the project or the experiment,
  by path, and stores its content. Without one it records the spec
  equivalent to today's freeze.
- **A freeze locks the tables it reads** on Postgres, and opens a write
  transaction on SQLite. Writers wait while it reads.
- **New commands:** `strata-catalog dataset verify`, and `strata-catalog
  list put | show | ls`.
- **`samples.matching` compares typed values** rather than strings, and
  it is the same code the spec's metadata conditions run. It still
  filters in Python, as record 0021 requires.
- **A condition on metadata with several origins** sees the combined
  view, so it inherits record 0049's stopgap: the first value wins.

## Revisions

- **Four changes are made in place, not two (revised as built).** This
  record named a tombstone and a withdrawn skip. Two more change what a
  replay reads, and each is now an event too. A sample's description,
  its subtype and metadata, is rewritten in place when a known sample is
  ingested again or a prepare run combines a new origin's facts (record
  0049). Its event keeps what it replaced, so a replay reads the
  description from before the watermark. An answer that arrives already
  superseded, as history `import-answers` carries from another catalog,
  can land after the current answer and have a higher id than it. Its
  event says it was never the answer here. Without these two events a
  replay would read today's metadata and, for some samples, an old
  answer as current. An event is written only when a description
  actually changes, and a sample a prepare run has just made has nothing
  to replace.
- **The command is `lists`, not `list` (revised as built).** `list`
  already prints the catalogs a host is configured for. So the commands
  are `strata-catalog lists put | show | ls`.
- **An included list restricts (decided as built, confirmed by the user).**
  The record said a list is included or excluded, and that the freeze
  counts how many members each one added or removed. As built, `include`
  keeps only the candidates whose checksums are in the list, and
  `exclude` drops those that are. Neither adds anything: a member still
  needs to be of a named type, in scope, with an answer that counts. A
  hand-picked set is then an include, and near-duplicates are an
  exclude. The freeze counts, for each list by itself, how many of the
  samples that passed the conditions it removed.
- **The spec a freeze without one records names the plain type of each
  media (revised as built).** The record said it names the types those
  collections hold. That would need every subtype's type installed on
  the host that freezes. The spec names the plain case of each media
  among the labelled samples instead, such as `text`. It covers every
  subtype, so it selects exactly what a freeze did before.
- **Members named outright record no spec (revised as built).**
  `create_dataset` still takes sample ids. A version frozen that way
  records no spec, and `dataset verify` says so, as it does for a version
  frozen before this record. Every freeze the dataset stage makes has a
  spec.
- **The first freeze after the migration is a new version (a consequence,
  noted as built).** The spec hash is part of a version's identity, and a
  version frozen before this record has none. Unknown is not a match
  (record 0024), so a freeze over unchanged members mints a new version
  once.
- **What a project and an experiment pass is not wired yet (TODO).** The
  dataset stage takes `spec`, a path, and stores its content. Neither the
  project config nor the labeller passes one yet, so they freeze as
  before, and record the equivalent spec.
