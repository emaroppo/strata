# auto-labeller

A semi-automatic image classification pipeline that integrates with [Label Studio](https://labelstud.io/) to close the loop between model training and human review. Instead of labelling thousands of images by hand, you label a small seed set, train a model, let it pre-label the rest, then only correct what it got wrong. Each round the model improves and there is less to fix.

---

## How it works

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│  Hand-label a   │────▶│  Train classifier │────▶│  Push predictions    │
│  seed set       │     │  (your CNN)       │     │  to Label Studio     │
│  (~50-100 imgs) │     │                  │     │  as pre-annotations  │
└─────────────────┘     └──────────────────┘     └──────────────────────┘
        ▲                                                    │
        │                                                    ▼
        │                                          ┌──────────────────────┐
        │     export corrected labels              │  Review & correct in  │
        └──────────────────────────────────────────│  Label Studio UI      │
                                                   └──────────────────────┘
```

**Each iteration:**
1. Label a small batch of images in Label Studio
2. Run `auto-labeller train` — fine-tunes your model on the labeled set
3. Run `auto-labeller push <project_id>` — runs inference on unlabeled images and sends predictions to Label Studio as pre-annotations, ordered from least to most confident
4. In Label Studio, review the pre-annotations: confirm the correct ones, fix the wrong ones
5. Run `auto-labeller export <project_id>` — pulls corrected labels back into the dataset JSON
6. Repeat from step 2 — each round has more labeled data and the model keeps improving

---

## Dataset format

All labeled and unlabeled images are tracked in a single JSON file. Each entry is an object with the image path and a list of labels. An empty label list means the image is unlabeled.

```json
[
  {"path": "data/raw/img001.jpg", "labels": ["cat", "indoor"]},
  {"path": "data/raw/img002.jpg", "labels": ["dog"]},
  {"path": "data/raw/img003.jpg", "labels": []}
]
```

Labels are lists, which means **multi-label classification is supported out of the box** — an image can belong to multiple classes simultaneously.

---

## Project structure

```
auto-labeller/
├── auto_labeller/
│   ├── config.py           # Settings loaded from config.toml and env vars
│   ├── model.py            # BaseModel ABC + Prediction dataclass
│   ├── dataset.py          # JSON dataset load / save / split utilities
│   ├── train.py            # Training orchestration and round bookkeeping
│   ├── predict.py          # Batch inference
│   ├── active_learning.py  # Uncertainty-based prioritisation for review
│   ├── ls_client.py        # Label Studio SDK wrapper
│   ├── ls_backend.py       # FastAPI ML backend server (live predictions in LS)
│   └── cli.py              # CLI entry points
├── data/
│   ├── raw/                # Your images go here
│   ├── rounds/             # Exported labels + metadata per round
│   │   └── round_001/
│   │       ├── metadata.json
│   │       └── labeled.json
│   └── dataset.json        # The single source of truth for the dataset
├── models/                 # Model checkpoints (round_001.pt, round_002.pt, ...)
├── docker-compose.yml      # Label Studio container
├── config.toml             # Configuration
└── pyproject.toml
```

---

## Setup

**1. Start Label Studio**

```bash
docker compose up -d
```

Label Studio is available at `http://localhost:8080`. Create an account on first launch. Your `data/raw/` folder is mounted inside the container, so images are served directly without uploading.

**2. Get your API key**

In Label Studio → Account & Settings → Access Token. Copy the token.

**3. Configure**

Edit `config.toml`:

```toml
[label_studio]
url = "http://localhost:8080"
api_key = ""  # paste your token here, or set LABEL_STUDIO_API_KEY env var

[paths]
dataset = "data/dataset.json"
images_dir = "data/raw"
checkpoints_dir = "models"
rounds_dir = "data/rounds"

[model]
module = "my_model"      # Python module name containing your model class
class_name = "MyModel"   # Class name inside that module
```

**4. Install dependencies**

```bash
uv sync
```

---

## Integrating your model

Create a Python file (e.g. `my_model.py`) in the project root and subclass `BaseModel`:

```python
from pathlib import Path
import torch
from auto_labeller.model import BaseModel, Prediction

class MyModel(BaseModel):
    def __init__(self):
        self.model = ...          # your nn.Module
        self.classes: list[str] = []

    def finetune(self, samples: list[dict], classes: list[str]) -> dict:
        # samples is a list of {"path": "...", "labels": ["cat"]} dicts
        # classes is the sorted full list of class names
        self.classes = classes
        # ... your training loop here ...
        return {"loss": avg_loss, "accuracy": acc}

    def predict(self, image_paths: list[Path]) -> list[Prediction]:
        # run inference and return one Prediction per image
        return [
            Prediction(
                path=str(p),
                labels=["cat"],        # top predicted label(s)
                confidences=[0.92],    # matching confidence scores
            )
            for p in image_paths
        ]

    def save(self, path: Path) -> None:
        torch.save({"model": self.model.state_dict(), "classes": self.classes}, path)

    def load(self, path: Path) -> None:
        checkpoint = torch.load(path, weights_only=True)
        self.model.load_state_dict(checkpoint["model"])
        self.classes = checkpoint["classes"]
```

Point `config.toml` at this file:

```toml
[model]
module = "my_model"
class_name = "MyModel"
```

---

## CLI reference

| Command | Description |
|---|---|
| `auto-labeller init <name>` | Create a Label Studio project and import all dataset tasks |
| `auto-labeller train` | Fine-tune the model on labeled data, save checkpoint + round metadata |
| `auto-labeller predict` | Run inference on unlabeled images and print results |
| `auto-labeller push <project_id>` | Push predictions to Label Studio as pre-annotations |
| `auto-labeller export <project_id>` | Pull corrected annotations from Label Studio into the dataset JSON |
| `auto-labeller serve` | Start the ML backend server for live predictions inside Label Studio |
| `auto-labeller report` | Print a round summary with delta metrics vs the previous round |

Every command accepts `--config-path` to point at a non-default `config.toml`.

### Full iteration example

```bash
# Round 1: you have hand-labeled ~50 images in dataset.json already
uv run auto-labeller init "my-project"   # creates LS project, note the project ID

uv run auto-labeller train               # trains round 1, saves models/round_001.pt

uv run auto-labeller push 1              # pushes predictions for unlabeled images
                                         # uncertain images appear first in LS

# ... review and correct labels in Label Studio ...

uv run auto-labeller export 1            # writes corrected labels back to dataset.json

# Round 2
uv run auto-labeller train
uv run auto-labeller push 1
# ... review ...
uv run auto-labeller export 1

uv run auto-labeller report              # compare round metrics
```

---

## Active learning

When you run `push`, predictions are sorted by model uncertainty so the most ambiguous images appear at the top of the Label Studio review queue. This means your annotation effort is concentrated where the model is most likely to be wrong.

Two uncertainty metrics are available internally (`least_confident` and `entropy`). The default is `least_confident` — images where the top predicted class has the lowest confidence are shown first.

Pass `--no-prioritize-uncertain` to push in original dataset order instead.

---

## Round bookkeeping

Each `train` run writes a `data/rounds/round_NNN/` directory:

```
round_001/
├── metadata.json   # timestamp, train/val/unlabeled counts, classes, metrics
└── labeled.json    # snapshot of the labeled data used for this round
```

`metadata.json` example:

```json
{
  "round": 1,
  "timestamp": "2026-05-06T14:32:00",
  "num_train": 40,
  "num_val": 10,
  "num_unlabeled": 200,
  "classes": ["cat", "dog", "bird"],
  "metrics": {"loss": 0.312, "accuracy": 0.875},
  "checkpoint": "models/round_001.pt"
}
```

`auto-labeller report` reads these files and prints a diff against the previous round.

---

## ML backend (live predictions)

For predictions to appear in Label Studio as you open each task, run the ML backend alongside Label Studio:

```bash
uv run auto-labeller serve   # starts FastAPI server on port 9090
```

Then in Label Studio → project Settings → Model, add the backend URL:

```
http://host.docker.internal:9090
```

The backend auto-loads the latest checkpoint at startup and forwards Label Studio prediction requests to your model.
