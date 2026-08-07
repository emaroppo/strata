"""What an annotation says, and what a model guesses it says.

Values are the payload of an annotation, independent of the task that
produced them and of any storage. One class per task type, discriminated on
``kind`` so a value round-trips out of JSON as the right type without the
reader knowing which task it came from.

A prediction is the same value plus the model's confidence in it, so ranking
and storage speak one shape rather than two that drift.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Value(BaseModel):
    """Base for every annotation payload."""

    kind: str

    model_config = {"frozen": True}


class Choices(Value):
    """One or more classes asserted about a whole sample."""

    kind: Literal["choices"] = "choices"
    values: list[str] = Field(default_factory=list)


class ChoicesPrediction(Choices):
    """:class:`Choices` a model produced, with its confidence per class."""

    confidences: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def _confidences_line_up(self) -> "ChoicesPrediction":
        if self.confidences and len(self.confidences) != len(self.values):
            raise ValueError(
                f"{len(self.values)} value(s) but {len(self.confidences)} "
                f"confidence(s); they are positional"
            )
        return self


#: Every annotation payload, discriminated on ``kind``. One member today —
#: adding boxes or spans is one class and one entry here.
AnyValue = Choices
