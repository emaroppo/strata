"""What an annotation says, and what a model guesses it says.

Values are the payload of an annotation, independent of the task that
produced them and of any storage. One class per task type, discriminated on
``kind`` so a value round-trips out of JSON as the right type without the
reader knowing which task it came from.

A prediction is the same value plus the model's confidence in it, so ranking
and storage speak one shape rather than two that drift.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


class Value(BaseModel):
    """Base for every annotation payload."""

    kind: str

    model_config = {"frozen": True}


class Prediction(Value):
    """A value a model produced, with how sure it was.

    A base rather than a field repeated on each type, so "this is model
    output" is something code can ask rather than infer. Confidences are
    positional against ``values``: the nth confidence belongs to the nth
    thing asserted, whether that is a class, a span or a box.
    """

    confidences: list[float] = Field(default_factory=list)


class Choices(Value):
    """One or more classes asserted about a whole sample."""

    kind: Literal["choices"] = "choices"
    values: list[str] = Field(default_factory=list)


class ChoicesPrediction(Choices, Prediction):
    """:class:`Choices` a model produced, with its confidence per class."""

    @model_validator(mode="after")
    def _confidences_line_up(self) -> "ChoicesPrediction":
        if self.confidences and len(self.confidences) != len(self.values):
            raise ValueError(
                f"{len(self.values)} value(s) but {len(self.confidences)} "
                f"confidence(s); they are positional"
            )
        return self


class Span(BaseModel):
    """A labelled character range inside a document.

    Offsets are what matter and are end-exclusive. ``text`` is carried
    because it makes a stored annotation readable without fetching the
    document, but it is a convenience: the offsets are authoritative.
    """

    label: str
    start: int
    end: int
    text: str = ""

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _range_is_forwards(self) -> "Span":
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"Not a range: start={self.start}, end={self.end}")
        return self


class Spans(Value):
    """Zero or more labelled ranges over one document."""

    kind: Literal["spans"] = "spans"
    values: list[Span] = Field(default_factory=list)

    @model_validator(mode="after")
    def _in_reading_order(self) -> "Spans":
        # Sorted on the way in so a stored annotation and a model's output
        # compare equal when they say the same thing
        object.__setattr__(
            self, "values", sorted(self.values, key=lambda s: (s.start, s.end))
        )
        return self


class SpansPrediction(Spans, Prediction):
    """:class:`Spans` a model produced, with its confidence per span."""


class Box(BaseModel):
    """A labelled rectangle over an image.

    Fractions of the image with a top-left origin, never pixels and never
    percentages. Label Studio speaks percentages alongside the original
    dimensions; converting at the boundary is what keeps a stored box
    meaningful without them.
    """

    label: str
    x: float
    y: float
    width: float
    height: float
    rotation: float = 0.0

    model_config = {"frozen": True}

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

#: Every payload a *model* produced. Separate from :data:`AnyValue` because
#: parsing a prediction as a plain value silently drops its confidences —
#: the extra field is simply not on the class, and pydantic discards what it
#: does not recognise. Anything holding model output has to say so, or it
#: keeps the answer and loses how sure the model was of it.
AnyPrediction = Annotated[
    ChoicesPrediction | SpansPrediction | BoxesPrediction,
    Field(discriminator="kind"),
]
