from .dataset import Sample
from .model import BaseModel, Prediction
from .project import Project


def run_predictions(
    model: BaseModel, samples: list[Sample], project: Project
) -> list[Prediction]:
    """Predict on samples, keeping prediction paths dataset-relative.

    The model works with absolute image paths; everything downstream keys
    off the data-root-relative sample path, so the paths are mapped back.
    """
    image_paths = [project.image_path(s.path) for s in samples]
    predictions = model.predict(image_paths)
    for prediction, sample in zip(predictions, samples):
        prediction.path = sample.path
    return predictions
