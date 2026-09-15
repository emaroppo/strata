"""What an annotation says, and what a model guesses it says.

Values are the payload of an annotation, independent of the task that
produced them and of any storage. One class per task type, discriminated on
``kind`` so a value round-trips out of JSON as the right type without the
reader knowing which task it came from.

A prediction is the same value plus the model's confidence in it. See
``docs/adr/0012``.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class Value(BaseModel):
    """Base for every annotation payload.

    Each concrete payload declares ``kind`` as the literal that names it,
    which is what :data:`AnyValue` discriminates on.
    """

    #: Frozen, and ``extra="forbid"`` so a misspelled field cannot build an
    #: empty value, which is an answer here (``docs/adr/0009``).
    model_config = {"frozen": True, "extra": "forbid"}


class Prediction(Value):
    """A value a model produced, with how sure it was.

    Confidences are positional against ``values``: the nth confidence
    belongs to the nth thing asserted, whether that is a class, a span or a
    box. See ``docs/adr/0012``.
    """

    confidences: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def _confidences_line_up(self) -> "Prediction":
        """Positional means positional, for every kind of prediction (``docs/adr/0012``)."""
        values = getattr(self, "values", None)
        if self.confidences and values is not None and len(self.confidences) != len(values):
            raise ValueError(
                f"{len(values)} value(s) but {len(self.confidences)} "
                f"confidence(s); they are positional"
            )
        return self


class Choices(Value):
    """One or more classes asserted about a whole sample."""

    kind: Literal["choices"] = "choices"
    values: list[str] = Field(default_factory=list)


class ChoicesPrediction(Choices, Prediction):
    """:class:`Choices` a model produced, with its confidence per class."""


class Span(BaseModel):
    """A labelled character range inside a document.

    Offsets are what matter and are end-exclusive. ``text`` is carried
    because it makes a stored annotation readable without fetching the
    document, but it is a convenience: the offsets are authoritative.

    **Labels, plural.** A region carrying two labels is *one* span with two
    labels, not two spans at the same offsets. Whether a label set permits
    either is :class:`~strata.labels.SpanSchema`'s to declare. See
    ``docs/adr/0014``.
    """

    labels: list[str] = Field(default_factory=list)
    start: int
    end: int
    text: str = ""

    model_config = {"frozen": True, "extra": "forbid"}

    @property
    def label(self) -> str:
        """The first label, or empty.

        Most spans carry exactly one, and this keeps that reading. Anything
        that has to be right about a multi-label region reads ``labels``.
        """
        return self.labels[0] if self.labels else ""

    @model_validator(mode="after")
    def _range_is_forwards(self) -> "Span":
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"Not a range: start={self.start}, end={self.end}")
        return self


class Spans(Value):
    """Zero or more labelled ranges over one document."""

    kind: Literal["spans"] = "spans"
    values: list[Span] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _in_reading_order(cls, data: object) -> object:
        # Sorted on the way in, labels breaking the tie, so two values that say
        # the same thing compare equal; confidences move under the same
        # permutation. docs/adr/0004
        if not isinstance(data, dict) or not data.get("values"):
            return data
        values = list(data["values"])
        try:
            order = sorted(range(len(values)), key=lambda i: _span_key(values[i]))
        except (AttributeError, KeyError, TypeError):
            return data  # malformed; field validation says what is wrong
        data = {**data, "values": [values[i] for i in order]}
        confidences = data.get("confidences")
        if confidences and len(confidences) == len(order):
            data["confidences"] = [confidences[i] for i in order]
        return data


def _span_key(span: object) -> tuple[int, int, tuple[str, ...]]:
    if isinstance(span, dict):
        return (span["start"], span["end"], tuple(span.get("labels", ())))
    return (span.start, span.end, tuple(span.labels))  # type: ignore[attr-defined]


class SpansPrediction(Spans, Prediction):
    """:class:`Spans` a model produced, with its confidence per span."""


class Box(BaseModel):
    """A labelled rectangle over an image.

    Fractions of the image with a top-left origin, never pixels and never
    percentages. See ``docs/adr/0013``.
    """

    label: str
    x: float
    y: float
    width: float
    height: float
    rotation: float = 0.0

    model_config = {"frozen": True, "extra": "forbid"}

    @model_validator(mode="after")
    def _fits_the_image(self) -> "Box":
        if self.width < 0 or self.height < 0:
            raise ValueError(f"Negative extent: {self.width}x{self.height}")
        if not all(0.0 <= v <= 1.0 for v in (self.x, self.y, self.width, self.height)):
            raise ValueError(
                f"Box is in fractions of the image, so every coordinate is 0..1; "
                f"got x={self.x}, y={self.y}, w={self.width}, h={self.height}"
            )
        return self


class Boxes(Value):
    """Zero or more labelled rectangles over one image."""

    kind: Literal["boxes"] = "boxes"
    values: list[Box] = Field(default_factory=list)


class BoxesPrediction(Boxes, Prediction):
    """:class:`Boxes` a model produced, with its confidence per box."""


#: Every annotation payload, discriminated on ``kind``.
AnyValue = Annotated[Choices | Spans | Boxes, Field(discriminator="kind")]

#: Every payload a *model* produced. Separate from :data:`AnyValue`: parsing
#: a prediction as a plain value drops its confidences (``docs/adr/0012``).
AnyPrediction = Annotated[
    ChoicesPrediction | SpansPrediction | BoxesPrediction,
    Field(discriminator="kind"),
]
