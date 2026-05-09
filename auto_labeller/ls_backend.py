import importlib
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel as PydanticBaseModel

from .config import Settings
from .model import BaseModel

app = FastAPI(title="auto-labeller ML backend")
_model: BaseModel | None = None
_settings: Settings | None = None


def _load_model(settings: Settings) -> BaseModel:
    module = importlib.import_module(settings.model.module)
    model_cls = getattr(module, settings.model.class_name)
    model: BaseModel = model_cls()

    checkpoint_dir = settings.paths.checkpoints_dir
    if checkpoint_dir.exists():
        checkpoints = sorted(checkpoint_dir.glob("round_*.pt"))
        if checkpoints:
            model.load(checkpoints[-1])
    return model


class PredictRequest(PydanticBaseModel):
    tasks: list[dict]
    project: str | None = None


@app.on_event("startup")
def startup() -> None:
    global _model, _settings
    _settings = Settings.load()
    _model = _load_model(_settings)


@app.get("/health")
def health() -> dict:
    return {"status": "UP"}


@app.post("/setup")
def setup() -> dict:
    return {"model_version": "latest"}


@app.post("/predict")
def predict(request: PredictRequest) -> dict:
    image_paths: list[Path] = []
    for task in request.tasks:
        image_url = task.get("data", {}).get("image", "")
        if "local-files" in image_url:
            path = "data/" + image_url.split("d=images/")[-1]
        else:
            path = image_url
        image_paths.append(Path(path))

    predictions = _model.predict(image_paths)

    results = []
    for pred in predictions:
        results.append(
            {
                "result": [
                    {
                        "from_name": "label",
                        "to_name": "image",
                        "type": "choices",
                        "value": {"choices": pred.labels},
                    }
                ],
                "score": max(pred.confidences) if pred.confidences else 0.0,
            }
        )
    return {"results": results}
