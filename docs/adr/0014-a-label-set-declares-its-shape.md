# 14. A label set declares its shape, and a model refuses before a round

**Status:** accepted

## The decision

A label set's schema is stored data: the task, its classes, and rules over
them. For spans it declares two things about shape, `multi_label` and
`overlapping`, both false by default and deliberately separate questions.
A model declares what it needs — the task, any classes of its own, any
features, and through `requires_schema` any shape it cannot represent —
and training refuses a mismatch before the round rather than during it.
The classes come from the label set, which is authoritative; a project's
file only seeds them.

## Why declared rather than inferred

Label Studio's model is a region with a *list* of labels, and it will let
a reviewer draw two regions across one phrase. Both are things an
annotation tool will happily produce and a model may be unable to learn.
BIO tagging gives each token one tag, so it can represent neither.
Without somewhere to say so, the tagger trains on a projection of the
label set and is scored as though it had learned the whole thing — and a
reviewer's stray overlap is stored as an answer nobody can use. An
annotation tool able to express more than the layer storing it is the
wrong way round, and the declaration is where the two are reconciled.

## What a Label Studio config can say about shape

The valid media and task combinations are not their product: boxes only
make sense on images and character spans only on text, so a template
exists for each pair that does. A project's own labeling config is read for
`multi_label`, since what the config permits is what reviewers will produce
and so what the label set has to accept; overlap has no attribute to read,
because Label Studio always allows it, so it stays declared in
`project.toml`. A region carrying two labels is one span with two labels,
not two spans at one offset. The boundary once read a region's first label
and dropped the rest, and nothing raised: the second label a reviewer
chose never reached the catalog.

## A schema is stored data

A schema is what a label set's row holds, so it is a pydantic model rather
than a class hierarchy with behaviour; the behaviour it carries is pure:
validating a value against the class list, and saying which classes a
value asserts. Spans once stored a single label and now carry a list, for
the reason above. Two spans at the same offsets are refused with a message
of their own, because that is what a multi-label region looks like when it
has been built as two spans, and the fix is one span with both labels
rather than a flag.

## Why a model declares its own classes

A model with an implicit negative class, such as a presence detector's
"none", predicts a class nothing else knows about. It gets no output
neuron, trains as an all-zeros target, and is emitted when no class clears
the threshold, so the model cannot contradict itself. Left undeclared, the
prediction is legal to the model and dropped by whatever displays it,
silently, and worst on exactly the samples worth reviewing; so the label
set has to declare it, and training refuses if it does not. The requirement
is read from the built model rather than the class, since it can depend on
a parameter, and the model is built before its requirements are read:
construction is seconds where the round is minutes, so a refusal still
comes before the expensive part.

## Why the refusal is before the round

A model pointed at the wrong task, or missing a class it emits, or a
feature nobody supplies, or a shape it cannot hold, would otherwise be
discovered by training on a projection of the data and reporting a number
for it. Each of these is caught on the side with the facts, when the
request is built, so the failure names what would be needed instead. The
default `requires_schema` accepts anything, because most models have
nothing to say.

## Why the label set holds the classes

Two class lists — one in the project's file, one in the catalog — drifted,
and a class added in the Label Studio UI or by hand silently put a
reviewer's answer beyond what the catalog would accept. The label set is
what an export is validated against and what a checkpoint maps its
outputs to, so it is authoritative; the file seeds it once and cannot
change behaviour afterwards. Classes are append-only (record 0005).

## Why windowing is a parameter, not a default

The right way to handle a document past an encoder's limit is not a
property of text; it depends on the corpus. Windowing suits mail, where
the tail of a long message carries as many entities as the head;
truncation suits a corpus whose documents lead with what matters. So the
choice is declared in the model's parameters and recorded on the run,
rather than inherited from a default nobody chose. The overlap between
windows defaults to a fraction of the window, because a fixed token count
is either too small for a long window or larger than a short one, and the
second silently means the windows never advance.

## How the text heads meet a label set

A sigmoid head scores every class independently, so it cannot promise to
name only one: a single-choice label set is refused, since a second class
would land as a pre-annotation a reviewer has to undo, on a control that
will not display it. A softmax head names exactly one, so a multi-choice
label set is refused too: it would train on the first answer and be scored
as though the rest had been asked for.

Windowing gives several answers for one document, and a classifier has to
combine them. There is no right default: `max` says a class is present if
any window was confident, `mean` averages the evidence, `any` takes the
union, and they disagree most on exactly the long documents windowing
exists for. So `window_aggregation` is required when a classifier windows,
and checked in the constructor, where a typo fails before a round rather
than at the first prediction. A single-label head does not offer `any`,
since the union is not an answer it may give. Every window of a document
carries the document's labels, because the target is a statement about the
whole and nothing says which window earned it. Each window is decoded to
its own winner before the merge, so a class that came second everywhere
never reaches it; keeping it would mean holding every window's logits, and
both heads share the limit so they stay consistent.

For spans, the tokenizer reports character offsets into the original
string for every window, so nothing is rebased afterwards, the step that
would otherwise most easily go wrong, and silently. An entity in the
overlap between two windows is found by both: it is one entity when the
label and both offsets agree, and the higher confidence wins, since the
window that saw it with more context is the one to believe. An entity
longer than the overlap is found in halves and reported as two, a known and
visible failure rather than a surprising one.

## Consequences

- An empty class list is allowed — a label set exists before anyone has
  decided what is in it — and validates nothing until classes are declared.
- The schema does not say what a sample is made of. Classifying a
  photograph and classifying a document are the same task; the media is
  the catalog's business, on the sample.
- A label set's schema is read back through a discriminator, so a catalog
  can hold boxes it can also hand back. An annotation is read the same way:
  read as one task's value, a boxes annotation parses without complaint
  into an empty choices value, and the catalog forgets what a person said.
