import json
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Sample:
    path: str
    labels: list[str] = field(default_factory=list)
    # Reviewed but no class fits: excluded from training and from the
    # unlabeled pool, so it never reappears in the review queue
    skipped: bool = False

    @property
    def is_labeled(self) -> bool:
        return len(self.labels) > 0


def load_dataset(path: Path) -> list[Sample]:
    with open(path) as f:
        data = json.load(f)
    return [Sample(**item) for item in data]


def save_dataset(samples: list[Sample], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = []
    for s in samples:
        item: dict = {"path": s.path, "labels": s.labels}
        if s.skipped:
            item["skipped"] = True
        data.append(item)
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
    """Split into (labeled, unlabeled); skipped samples belong to neither."""
    labeled = [s for s in samples if s.is_labeled and not s.skipped]
    unlabeled = [s for s in samples if not s.is_labeled and not s.skipped]
    return labeled, unlabeled


def train_val_split(
    samples: list[Sample],
    val_ratio: float = 0.2,
    seed: int = 42,
    group_key: Callable[[Sample], str] | None = None,
) -> tuple[list[Sample], list[Sample]]:
    """Split samples into train/val.

    With group_key, whole groups (e.g. all frames of one video) land on the
    same side of the split so near-duplicate frames can't leak into val.
    """
    rng = random.Random(seed)
    if group_key is None:
        shuffled = list(samples)
        rng.shuffle(shuffled)
        split_idx = int(len(shuffled) * (1 - val_ratio))
        return shuffled[:split_idx], shuffled[split_idx:]

    groups: dict[str, list[Sample]] = {}
    for s in samples:
        groups.setdefault(group_key(s), []).append(s)
    keys = sorted(groups)
    rng.shuffle(keys)

    target_val = int(len(samples) * val_ratio)
    train: list[Sample] = []
    val: list[Sample] = []
    for key in keys:
        bucket = val if len(val) < target_val else train
        bucket.extend(groups[key])
    return train, val
