"""Image classification: one or more classes per image."""

import math
from dataclasses import dataclass, field

from .base import LabelSchema, Result, strip_volatile
from .render import render_template


@dataclass
class ChoiceOutput:
    """What a classifier hands back: its chosen labels and their confidence.

    The model owns the decision (threshold, argmax, negative class); the
    schema owns turning that decision into Label Studio's wire format.
    """

    labels: list[str] = field(default_factory=list)
    confidences: list[float] = field(default_factory=list)


class ClassificationSchema(LabelSchema):
    type = "image_classification"
    data_key = "image"
    control_tag = "Choices"

    def __init__(
        self,
        classes: list[str],
        choice: str = "multiple",
        from_name: str = "label",
        to_name: str = "image",
    ):
        self.classes = list(classes)
        self.choice = choice
        self.from_name = from_name
        self.to_name = to_name

    # ------------------------------------------------------------------
    # Label Studio config
    # ------------------------------------------------------------------

    def label_config(self) -> str:
        return render_template(
            self.type,
            classes=self.classes,
            label_tag="Choice",
            from_name=self.from_name,
            to_name=self.to_name,
            choice=self.choice,
        )

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def canonicalize(self, results: list[dict]) -> list[Result]:
        return [
            strip_volatile(r) for r in results if r.get("type") == "choices"
        ]

    def decode_target(self, results: list[Result]) -> list[str]:
        return [
            choice
            for r in results
            for choice in r.get("value", {}).get("choices", [])
        ]

    def encode_target(self, target: list[str]) -> list[Result]:
        if not target:
            return []
        return [
            {
                "from_name": self.from_name,
                "to_name": self.to_name,
                "type": "choices",
                "value": {"choices": list(target)},
            }
        ]

    def encode_output(self, output: ChoiceOutput) -> list[Result]:
        return self.encode_target(output.labels)

    # ------------------------------------------------------------------
    # Active learning
    # ------------------------------------------------------------------

    def score(self, output: ChoiceOutput) -> float:
        return max(output.confidences, default=0.0)

    def uncertainty(self, output: ChoiceOutput) -> float:
        """Least-confident: the lower the top confidence, the sooner to review."""
        return 1.0 - self.score(output)

    @staticmethod
    def entropy(confidences: list[float]) -> float:
        return -sum(c * math.log(c + 1e-10) for c in confidences if c > 0)

    def classes_in_use(self, results_lists: list[list[Result]]) -> list[str]:
        seen: set[str] = set()
        for results in results_lists:
            seen.update(self.decode_target(results))
        return sorted(seen)
