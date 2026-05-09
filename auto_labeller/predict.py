from pathlib import Path

from .dataset import Sample
from .model import BaseModel, Prediction


def run_predictions(
    model: BaseModel, samples: list[Sample]
) -> list[Prediction]:
    image_paths = [Path(s.path) for s in samples]
    return model.predict(image_paths)
