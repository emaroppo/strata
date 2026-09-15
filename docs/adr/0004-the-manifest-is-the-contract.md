# 4. The manifest is the contract between catalog and modelling, and `labels` holds it

**Status:** accepted

## The decision

A materialised dataset is a directory of files named by checksum and a
`manifest.json` complete enough that nothing needs a database to train
from it. The manifest's definition lives in `strata.labels`, the one
package both the writer (catalog) and the reader (modelling) may import.
It states its format number, and a reader refuses a format it does not
know.

## Why the definition lives in the leaf

The catalog writes it and modelling reads it, and neither may import the
other. When the manifest lived in the catalog, modelling read it back by
key name — and a renamed field arrived as nothing rather than as an error.
Reading through the manifest's own definition is what makes a rename fail
where it happens.

`labels` is the leaf because it is pure: the standard library and pydantic,
no I/O, no storage, no framework, and never Label Studio. The same
definitions then serve storage, the manifest and modelling's request
types, so a value has one description rather than three that drift. A
change there is a wire-format change and is treated as one.

## Why a format number, and when it moves

Once the packages ship separately, the release that wrote a manifest need
not be the one reading it. The number goes up only when an older reader
would *misread* a newer file — a field whose meaning changed, a value it
would take for something else. A field added with a default does not
bump it: pydantic ignores fields it does not know, which is exactly why
that case is safe and the other is not. The third side of the split was
added with room already made, and did not bump the format.

## Why every layer reads a value through the union

A label type is defined in `labels` and handled in several places: the
catalog stores it, a manifest carries it, modelling reads it and caches
predictions of it, the labeller shows it and ranks a queue by it. So every
layer reads a value through the union of types rather than one of them. A
manifest sample's value is any annotation payload, since a dataset version
is what a model trains from, and pinning it to choices would mean no
detector could ever be handed one. A model's `Example.target` is the union,
since naming one concrete type would say a model can only be trained on
that kind. What a scoring pass returns carries the union of predictions:
naming one concrete type there once refused every span and box prediction
on the way out, the last place a value travels before the review queue is
ranked. The conformance suite's table of what each task emits is not a
plugin surface; a new label type is added to `labels` first.

`labels` ships one example of every label type, and each package that
handles label types tests its own layer against all of them. A type added
there fails in every package the next time it upgrades, loudly, until it is
handled, and no test reaches across a package boundary to find it. A test in
`labels` refuses a type in the unions that has no example.

## Consequences

- The training core takes a directory and a manifest and nothing else.
  That is what lets it be tested against a fixture directory with no
  database in sight, and run on a machine that has never heard of a
  catalog. Materialising is the shell's job.
- `examples()` in modelling is public: it is the last layer between a
  reviewer's answer and a model, and every label type is tested through it.
- The manifest carries the checksum beside the catalog-local id, so a
  different catalog can match its samples (record 0001), and it carries the
  catalog's identity, so a directory says what built it (record 0008).
- Features travel in it as plain JSON, not as label values (record 0011).
- Two values that say the same thing compare equal. `Spans` sorts its
  ranges into reading order as it is parsed, by offset and then by labels,
  and a prediction's confidences move under the same permutation because
  they are positional. The sort runs over the raw payload, before the
  model is built, rather than writing into the frozen model afterwards: a
  value is frozen because it is a record of what someone said, and a type
  that goes around its own `frozen` is the one place that promise is
  not kept.
