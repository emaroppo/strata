import json
from datetime import datetime
from pathlib import Path

from .config import Settings
from .dataset import (
    get_classes,
    load_dataset,
    save_dataset,
    split_labeled_unlabeled,
    train_val_split,
)
from .model import BaseModel


def run_training(
    model: BaseModel,
    settings: Settings,
    round_num: int | None = None,
) -> dict:
    dataset = load_dataset(settings.paths.dataset)
    labeled, unlabeled = split_labeled_unlabeled(dataset)
    classes = get_classes(labeled)

    if not labeled:
        raise ValueError("No labeled samples found in dataset")

    train_samples, val_samples = train_val_split(labeled)

    if round_num is None:
        round_num = _next_round_num(settings.paths.rounds_dir)

    metrics = model.finetune(
        [{"path": s.path, "labels": s.labels} for s in train_samples],
        classes,
    )

    checkpoint_path = settings.paths.checkpoints_dir / f"round_{round_num:03d}.pt"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(checkpoint_path)

    round_dir = settings.paths.rounds_dir / f"round_{round_num:03d}"
    round_dir.mkdir(parents=True, exist_ok=True)

    round_meta = {
        "round": round_num,
        "timestamp": datetime.now().isoformat(),
        "num_train": len(train_samples),
        "num_val": len(val_samples),
        "num_unlabeled": len(unlabeled),
        "classes": classes,
        "metrics": metrics,
        "checkpoint": str(checkpoint_path),
    }
    with open(round_dir / "metadata.json", "w") as f:
        json.dump(round_meta, f, indent=2)

    save_dataset(labeled, round_dir / "labeled.json")

    return round_meta


def _next_round_num(rounds_dir: Path) -> int:
    if not rounds_dir.exists():
        return 1
    existing = [
        d
        for d in rounds_dir.iterdir()
        if d.is_dir() and d.name.startswith("round_")
    ]
    if not existing:
        return 1
    return max(int(d.name.split("_")[1]) for d in existing) + 1
