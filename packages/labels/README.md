# strata-labels

What an annotation is, independent of who produced it or where it is
stored. The one package every other strata package imports, so a value has
one description rather than three that drift.

```bash
uv add strata-labels
```

Depends on pydantic and nothing else. May not import anything that does
I/O, any storage layer, any ML framework, or Label Studio.

## What it holds

**Values** are the payload of an annotation, one per task type,
discriminated on `kind` so a value round-trips out of JSON as the right
type without the reader knowing which task it came from:

| kind | value | prediction |
|---|---|---|
| `choices` | `Choices` — classes asserted about a whole sample | `ChoicesPrediction` |
| `spans` | `Spans` — labelled character ranges in a document | `SpansPrediction` |
| `boxes` | `Boxes` — labelled rectangles over an image | `BoxesPrediction` |

`AnyValue` and `AnyPrediction` are the unions. A prediction is the same
value plus a confidence per thing asserted, positional against `values`.
An empty value is an answer: a reviewer looked and found none of the
classes present. Values are frozen and forbid unknown fields, because a
typo that produced an empty value would land in a catalog as that answer.

**Schemas** describe a label set: the task, its classes, and the rules
over them. `ClassificationSchema`, `SpanSchema` and `BBoxSchema`, with
`AnySchema` as the union. Each validates a value against its class list
and answers the indexing contract, *which classes does this value assert*,
which is what lets a catalog index annotations it does not otherwise
understand. A span schema also declares its shape, `multi_label` and
`overlapping`, so a model can refuse before a round.

**The manifest** is what a trainer is handed: `Manifest` and
`ManifestSample`, written by the catalog beside a materialised dataset and
read by modelling, complete enough that nothing needs a database to train
from it. It states `MANIFEST_FORMAT`, and a reader refuses a format it
does not know. `feature_digest` is the digest of a sample's features that
keys the prediction cache.

**Examples.** `strata.labels.examples` holds a sample of every type. Each
consuming package tests its own layer against all of them, so a type added
here fails in each package until that package handles it.

## Decisions

Recorded in the strata umbrella repository's `docs/adr/` (https://github.com/emaroppo/strata/tree/main/docs/adr): the manifest as the
contract between catalog and modelling (0004), the prediction cache's third
input (0006), features as plain JSON (0011), and a label set declaring its
shape (0014).

## Tests

```bash
uv sync --find-links dist --group dev
uv run pytest
```

Inside the strata workspace: `uv run pytest packages/labels` from its root.
