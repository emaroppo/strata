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

## Consequences

- An empty class list is allowed — a label set exists before anyone has
  decided what is in it — and validates nothing until classes are declared.
- The schema does not say what a sample is made of. Classifying a
  photograph and classifying a document are the same task; the media is
  the catalog's business, on the sample.
- A label set's schema is read back through a discriminator, so a catalog
  can hold boxes it can also hand back.
