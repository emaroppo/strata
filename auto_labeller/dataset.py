import json
import random
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Sample:
    path: str
    labels: list[str] = field(default_factory=list)

    @property
    def is_labeled(self) -> bool:
        return len(self.labels) > 0


def load_dataset(path: Path) -> list[Sample]:
    with open(path) as f:
        data = json.load(f)
    return [Sample(**item) for item in data]


def save_dataset(samples: list[Sample], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [{"path": s.path, "labels": s.labels} for s in samples]
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_classes(samples: list[Sample]) -> list[str]:
    classes: set[str] = set()
    for s in samples:
        classes.update(s.labels)
    return sorted(classes)


def split_labeled_unlabeled(
    samples: list[Sample],
) -> tuple[list[Sample], list[Sample]]:
    labeled = [s for s in samples if s.is_labeled]
    unlabeled = [s for s in samples if not s.is_labeled]
    return labeled, unlabeled


def train_val_split(
    samples: list[Sample],
    val_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[Sample], list[Sample]]:
    rng = random.Random(seed)
    shuffled = list(samples)
    rng.shuffle(shuffled)
    split_idx = int(len(shuffled) * (1 - val_ratio))
    return shuffled[:split_idx], shuffled[split_idx:]
