"""A sample of every label type, for the tests of any package that handles them.

A label type is defined here and handled in several places: the catalog
stores it, a manifest carries it, modelling reads it and caches predictions
of it, the labeller shows it in Label Studio and ranks a queue by it. Each
of those tests its own layer against every example below. So a type added
here is covered by every package the next time that package upgrades — and
fails there, loudly, until it is handled — without any test having to reach
across a package boundary to find it.

Adding a label type means adding an example of it here; a test in this
package refuses a type in the unions that has none.
"""

from dataclasses import dataclass

from .schema import AnySchema, BBoxSchema, ClassificationSchema, SpanSchema
from .values import (
    AnyPrediction,
    AnyValue,
    Box,
    Boxes,
    BoxesPrediction,
    Choices,
    ChoicesPrediction,
    Span,
    Spans,
    SpansPrediction,
)


@dataclass(frozen=True)
class LabelTypeExample:
    """One label type, as each layer needs to see it."""

    #: What a test run calls it.
    name: str
    schema: AnySchema
    #: An annotation of this type, as a person would have left it.
    value: AnyValue
    #: A model's output of this type, with a confidence per thing asserted.
    prediction: AnyPrediction
    #: What the samples carrying it are, as the catalog records them. Spans
    #: are character ranges in a document, so theirs are text.
    media: str = "image"


EXAMPLES: tuple[LabelTypeExample, ...] = (
    LabelTypeExample(
        name="choices",
        schema=ClassificationSchema(classes=["cat", "dog"]),
        value=Choices(values=["cat"]),
        prediction=ChoicesPrediction(values=["cat", "dog"], confidences=[0.9, 0.2]),
    ),
    LabelTypeExample(
        name="spans",
        schema=SpanSchema(classes=["name", "place"]),
        value=Spans(values=[Span(labels=["name"], start=0, end=4)]),
        prediction=SpansPrediction(
            values=[Span(labels=["name"], start=0, end=4)], confidences=[0.8]
        ),
        media="text",
    ),
    # A region carrying two labels. Label Studio could always express it;
    # the layer storing it once dropped the second label without a word.
    LabelTypeExample(
        name="multi-label spans",
        schema=SpanSchema(classes=["name", "place"], multi_label=True),
        value=Spans(values=[Span(labels=["name", "place"], start=0, end=4)]),
        prediction=SpansPrediction(
            values=[Span(labels=["name", "place"], start=0, end=4)], confidences=[0.8]
        ),
        media="text",
    ),
    # Two regions that intersect, where the label set says they may.
    LabelTypeExample(
        name="overlapping spans",
        schema=SpanSchema(classes=["name", "place"], overlapping=True),
        value=Spans(
            values=[Span(labels=["name"], start=0, end=8), Span(labels=["place"], start=4, end=12)]
        ),
        prediction=SpansPrediction(
            values=[Span(labels=["name"], start=0, end=8), Span(labels=["place"], start=4, end=12)],
            confidences=[0.8, 0.4],
        ),
        media="text",
    ),
    LabelTypeExample(
        name="boxes",
        schema=BBoxSchema(classes=["cat", "dog"]),
        value=Boxes(values=[Box(label="cat", x=0.1, y=0.2, width=0.3, height=0.4)]),
        prediction=BoxesPrediction(
            values=[Box(label="cat", x=0.1, y=0.2, width=0.3, height=0.4)], confidences=[0.7]
        ),
    ),
)

__all__ = ["EXAMPLES", "LabelTypeExample"]
