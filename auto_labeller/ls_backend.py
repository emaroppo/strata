"""FastAPI ML backend serving live predictions to Label Studio.

The project to serve comes from the AUTO_LABELLER_PROJECT environment
variable (set by ``auto-labeller serve --project``), since uvicorn imports
this module rather than calling into it.
"""

from pathlib import Path
from urllib.parse import unquote

from fastapi import FastAPI
from pydantic import BaseModel as PydanticBaseModel

from .model import BaseModel
from .project import Project

app = FastAPI(title="auto-labeller ML backend")
_model: BaseModel | None = None
_project: Project | None = None


class PredictRequest(PydanticBaseModel):
    tasks: list[dict]
    project: str | None = None


@app.on_event("startup")
def startup() -> None:
    global _model, _project
    _project = Project.load()
    _model = _project.load_model()
    checkpoint = _project.latest_checkpoint()
    if checkpoint:
        _model.load(checkpoint)


@app.get("/health")
def health() -> dict:
    return {"status": "UP"}


@app.post("/setup")
def setup() -> dict:
    return {"model_version": "latest"}


@app.post("/predict")
def predict(request: PredictRequest) -> dict:
    assert _model is not None and _project is not None
    prefix = _project.label_studio.local_files_prefix

    image_paths: list[Path] = []
    for task in request.tasks:
        image_url = task.get("data", {}).get("image", "")
        if "local-files" in image_url:
            rel = unquote(image_url.split(f"d={prefix}/", 1)[-1])
            image_paths.append(_project.image_path(_project.sample_path_from_mount(rel)))
        else:
            image_paths.append(Path(image_url))

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
