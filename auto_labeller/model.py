from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Prediction:
    path: str
    labels: list[str]
    confidences: list[float]


class BaseModel(ABC):
    """Subclass this and implement the four methods below.

    Your model (e.g. a ``torch.nn.Module``) should be stored as an
    instance attribute so that ``finetune`` and ``predict`` can access it.
    """

    @abstractmethod
    def finetune(self, samples: list[dict], classes: list[str]) -> dict:
        """Fine-tune on labeled data.

        ``samples`` is a list of dicts, each with keys ``"path"`` (str)
        and ``"labels"`` (list[str]).  ``classes`` is the full class list.

        Return a metrics dict, e.g. ``{"loss": 0.12, "accuracy": 0.93}``.
        """
        ...

    @abstractmethod
    def predict(self, image_paths: list[Path]) -> list[Prediction]:
        """Return one ``Prediction`` per image path."""
        ...

    @abstractmethod
    def save(self, path: Path) -> None:
        ...

    @abstractmethod
    def load(self, path: Path) -> None:
        ...
