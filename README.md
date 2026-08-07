# auto-labeller

A semi-automatic labelling pipeline that integrates with [Label Studio](https://labelstud.io/) to close the loop between model training and human review. Instead of labelling thousands of samples by hand, you label a small seed set, train a model, let it pre-label the rest, then only correct what it got wrong. Each round the model improves and there is less to fix.

Images and text documents are both supported, for whole-sample classification, bounding boxes, or character spans — a project declares which, and everything else follows from that.

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
3. Run `auto-labeller push` — runs inference on unlabeled images and sends predictions to Label Studio as pre-annotations, ordered from least to most confident
4. In Label Studio, review the pre-annotations: confirm the correct ones, fix the wrong ones
5. Run `auto-labeller export` — pulls corrected labels back into the dataset JSON
6. Repeat from step 2 — each round has more labeled data and the model keeps improving

---

## Dataset format

All labeled and unlabeled images are tracked in a single JSON file per project. Annotations are stored as **canonicalized Label Studio results** — the format Label Studio itself speaks, with the volatile fields (ids, timestamps, lead time) stripped:

```json
{
  "version": 2,
  "samples": [
    {"path": "img001.jpg", "annotated": true, "results": [
      {"from_name": "label", "to_name": "image", "type": "choices",
       "value": {"choices": ["cat", "indoor"]}}
    ]},
    {"path": "batch2/img002.jpg"},
    {"path": "batch2/img003.jpg", "skipped": true}
  ]
}
```

Paths are relative to the project's `[data] root`. Storing Label Studio's own shape means predictions and annotations are one format, any control type fits without a schema change here, and the existing conversion tools (`label-studio-converter` and friends) apply directly to a handed-off project.

`annotated` says a human answered, which is not the same as the answer being non-empty: an image with no boxes on it is a real annotation, and only this flag distinguishes it from one nobody has looked at. `skipped` marks a task skipped in Label Studio — reviewed, but nothing applies. Skipped images are excluded from both training and the unlabeled pool, so they never reappear in the review queue; `unskip` brings them back.

Multi-label classification works out of the box, since a `choices` value is a list.

The earlier v1 format (a bare list of `{"path", "labels"}`) is still read — the loader upgrades it on the way in. To convert the files on disk, including round snapshots:

```bash
uv run python scripts/migrate_dataset_v2.py -p <project> --dry-run   # then without --dry-run
```

---

## Projects

A **project** is a directory holding everything that belongs to one labelling job — data, label schema, annotations, model, and checkpoints — so that once labelling is done you can pick up the folder and use it elsewhere. The tool is the machine; the project is the work.

Projects live side by side under `projects/`:

```
projects/
├── my-project/
│   ├── project.toml        # label schema, data root, model, LS project id
│   ├── dataset.json        # samples + annotations (paths relative to the data root)
│   ├── data/raw/           # the images
│   ├── model.py            # optional: a model this project carries
│   ├── checkpoints/        # round_001.pt, round_002.pt, ...
│   ├── rounds/round_001/   # metadata.json + labeled.json per round
│   └── .state/             # Label Studio bookkeeping — not part of a handoff
└── traffic-signs/
    └── ...
```

```toml
# project.toml
name = "my-project"

[label_config]
template = "image_classification"
classes  = ["cat", "dog"]
choice   = "multiple"            # "single" for mutually exclusive classes

[data]
root = "data/raw"                # may be an absolute path for a shared corpus
kind = "images"                  # "frames" for video frames, one folder per video

[model]
ref = "presence"

[model.params]
num_epochs = 4
batch_size = 16
lr = 5e-5

[label_studio]
project_id = 42                  # written by `auto-labeller init`
```

Every command takes `--project/-p`, which accepts a project name under `projects/` or any path — so switching jobs is one word:

```bash
auto-labeller projects                  # what's here, with class and label counts
auto-labeller train -p my-project
auto-labeller train -p traffic-signs
```

With a single project, `-p` can be omitted entirely; with several, set `AUTO_LABELLER_PROJECT` to pick a default for the shell. `projects/` is gitignored in full: project data stays local, and this repository holds only the tool.

Sample paths in `dataset.json` are relative to `[data] root`, so moving the project — or repointing it at the same images somewhere else — never rewrites the dataset.

`[data] kind` says how the samples relate to each other, which is what the train/val split needs to know:

| `kind` | Layout | Split |
| --- | --- | --- |
| `images` (default) | Whatever suits you; folders are just folders | Samples are independent, so they are shuffled and split individually |
| `frames` | One folder per video, its frames inside | Whole videos land on one side of the split |

Frames a fraction of a second apart are near-duplicates. Splitting them individually would put a frame in validation whose neighbours the model trained on, and the resulting score measures memorisation rather than generalisation — so under `kind = "frames"` a video is indivisible.

---

## Label schemas

A project's `[label_config] template` picks both the Label Studio labeling config and the **schema** that reads it. The schema is the only place that knows what a task type looks like: it generates the config, converts between stored results and what the model consumes, and defines what "uncertain" means for the review queue.

```bash
uv run auto-labeller templates                                    # what is available
uv run auto-labeller new docs --template text_classification --class spam --class ham
```

| Template | Files | Annotations | Model sees |
|---|---|---|---|
| `image_classification` | images | `<Choices>` | `list[str]` in, `ChoiceOutput` out |
| `image_bbox` | images | `<RectangleLabels>` | `list[Box]` in, `BoxOutput` out, coordinates as fractions |
| `text_classification` | `.txt`, `.md` | `<Choices>` | `list[str]` in, `ChoiceOutput` out |
| `text_span` | `.txt`, `.md` | `<Labels>` | `list[Span]` in, `SpanOutput` out, character offsets |
| `custom` | per its media tag | per its control | per the control it finds |

**Media is orthogonal to task.** A media type declares its Label Studio tag, the key tasks are read from, and the extensions `ingest` accepts; a task type declares the annotation shape. Templates are the valid combinations rather than their product, since boxes only make sense on images and character spans only on text. Documents are served from the same local-files mount images use (`valueType="url"`), so paths, the task-id cache and export work identically whatever a project labels.

`template = "custom"` hands your own `label_config.xml` to Label Studio verbatim and derives the schema by parsing it — media, control names and classes all come from the XML, because that is what annotations reference. Declaring `classes` in `project.toml` alongside it is an error rather than a second source of truth waiting to drift.

Uncertainty is schema-owned, because it does not generalise: classification ranks by least confidence, while detection and span tagging rank by proximity to the decision threshold and treat a sample with nothing found as maximally uncertain — the model either found nothing or missed everything, and only a human settles which.

Adding a task type means adding a schema and a template. Nothing in `ls_client`, `train`, `predict`, `active_learning` or the CLI changes.

---

---

## Repository layout

A `uv` workspace, mid-restructuring — see `docs/roadmap.md`. `labels`,
`catalog` and `modelling` are built; `labeller` still owns the Label Studio
integration and the round loop, and moves onto the catalog at the cutover.

```
auto-labeller/
├── packages/
│   ├── labels/    strata/labels/     # what an annotation is: values and schemas
│   ├── catalog/   strata/catalog/    # samples, storage, annotations, datasets
│   ├── modelling/ strata/modelling/  # train/predict, runs, and the baselines
│   └── labeller/
│       ├── strata/labeller/
│       │   ├── project.py          # the Project construct: paths, schema, model loading
│       │   ├── schemas/            # one module per task type + the template registry
│       │   ├── label_configs/      # packaged Label Studio config templates
│       │   ├── config.py           # host settings (Label Studio URL + API key)
│       │   ├── dataset.py          # JSON dataset load / save / split utilities
│       │   ├── train.py            # Training orchestration and round bookkeeping
│       │   ├── predict.py          # Batch inference
│       │   ├── active_learning.py  # Uncertainty-based prioritisation for review
│       │   ├── ls_client.py        # Label Studio SDK wrapper
│       │   ├── ls_backend.py       # FastAPI ML backend server (live predictions in LS)
│       │   └── cli.py              # CLI entry points
│       ├── tests/          # the suite; most of it runs without a framework
│       └── scripts/        # one-off utilities (e.g. migration)
├── docs/                   # architecture and roadmap
├── projects/               # your labelling projects (payload gitignored)
├── docker-compose.yml      # Label Studio container
├── config.example.toml     # host settings template
└── pyproject.toml          # workspace root: shared lint, test and dev config
```

---

## Setup

**1. Start Label Studio**

```bash
docker compose up -d
```

Label Studio is available at `http://localhost:8080`. Create an account on first launch. The active project's `data/` folder is mounted inside the container, so images are served directly without uploading.

**2. Get your API key**

In Label Studio → Account & Settings → Access Token. Copy the token.

**3. Configure this machine**

Copy `config.example.toml` to `config.toml` (gitignored) and paste your token — or set `LABEL_STUDIO_API_KEY` instead:

```toml
[label_studio]
url = "http://localhost:8080"
api_key = ""
local_storage_path = "/label-studio/data/images"
```

That file holds *only* host settings. Everything about a labelling job lives in its project.

**4. Install dependencies**

```bash
uv sync --extra image     # or --extra text, or --extra all
```

The base install carries no ML framework — only the pipeline itself, which needs nothing heavier than the Label Studio SDK. Torch and friends come with the extra for the media you are labelling, because they are needed by exactly one thing: the [baseline models](#the-model). A project pointing `[model] ref` at its own `model.py` can stay on the base install and bring whatever framework it likes.

| Extra | Pulls in | For |
|---|---|---|
| `image` | torch, torchvision, timm, Pillow | the image baselines |
| `text` | torch, transformers | the text baselines |
| `all` | both | |

Asking for a baseline you have not installed the extra for fails at `train`/`predict` time with a message naming the extra, not a stray `ModuleNotFoundError`.

**5. Create a project**

```bash
uv run auto-labeller new cats --class cat --class dog   # creates projects/cats/
cp -r /path/to/images/* projects/cats/data/raw/
uv run auto-labeller ingest -p cats
```

Set `AUTO_LABELLER_PROJECT=projects/cats` before `docker compose up` so Label Studio mounts that project's images.

---

## Tests

```bash
uv run pytest        # the whole suite
uv run ruff check .  # lint
```

The suite splits along the same line the dependencies do. Most of it — the schema conversions, the dataset format, project resolution and paths, config editing, the model ref contract — imports no ML framework and runs on the base install. The rest covers the image baselines' task hooks, the letterbox transform and warm start, and skips with a message when the `image` extra is absent.

That split is deliberate: running the framework-free suite on a bare install is what keeps the [optional extras](#setup) honest. If anything on that path grows a `torch` import, collection fails there rather than in someone else's `pip install`.

Warm start is tested against a stub backbone rather than the real one, since building the real backbone downloads pretrained weights, and a unit test should not. The one piece still uncovered is a real `finetune` run: nothing yet asserts that training moves the weights, or exercises the round → checkpoint → metadata path end to end.

CI runs lint, then the suite twice — once on the base install and once with `--extra all`.

---

## The model

A project's model is declared by `[model] ref`, in one of two forms:

```toml
ref = "presence"             # a registered name
ref = "model.py:MyModel"     # this project's own model
ref = "mypkg.models:Custom"  # anything importable
```

A name without a `:` is looked up in the `strata.models` entry point group, so it need not be an import path — which is what lets a training request name a model over a wire. Anything with a `:` is a direct reference. The `*.py:Class` form loads the file from inside the project directory, so a project with a bespoke architecture stays self-contained. `[model.params]` is passed to the constructor.

Registering is the extension point: a distribution advertising `strata.models` entry points adds models without a change here, and `pkg.module:Class` works for anything already importable. That is why the frameworks are [optional extras](#setup) and the baselines import on demand.

Baselines live in `strata.modelling.baselines`. The image models are ConvNeXt V2 Base fine-tunes sharing one training loop and differing only in their task hooks; the text models fine-tune a Hugging Face encoder, DistilBERT by default:

| Name | Class | Task | Regime |
|---|---|---|---|
| `multilabel` | `MultiLabelClassifier` | classification | Independent sigmoids, BCE loss — an image can carry several classes |
| `multiclass` | `MulticlassClassifier` | classification | Softmax + cross-entropy — classes are mutually exclusive |
| `presence` | `PresenceClassifier` | classification | "Is X present?" detectors with an implicit `none` class for reviewed-but-empty images |
| `text` | `TextClassifier` | classification | Sequence classification with a sigmoid head, multi-label |
| `text-span` | `TextSpanTagger` | span | Token classification in BIO tagging, decoded back to character offsets |

Pick the encoder with `[model.params] encoder = "roberta-base"` or any Hugging Face id. A model declares the task it is written for, so pointing a span model at a classification label set fails before training starts rather than midway.

To write your own, subclass `Model` in a `model.py` inside the project:

```python
from pathlib import Path
import torch
from strata.labels import ChoicesPrediction
from strata.modelling import Example, Model

class MyModel(Model):
    task = "classification"
    version = "1"          # bump when old checkpoints stop loading

    def __init__(self, num_epochs: int = 4):   # filled from [model.params]
        self.model = ...                       # your nn.Module
        self.classes: list[str] = []

    def finetune(self, train: list[Example], classes: list[str],
                 val: list[Example] | None = None) -> dict:
        # each Example has .path and .target, a strata.labels value
        self.classes = classes
        # ... your training loop here ...
        return {"loss": avg_loss, "accuracy": acc, "val_loss": vl, "val_accuracy": va}

    def predict(self, paths: list[Path]) -> list[ChoicesPrediction]:
        # one prediction per path, in order
        return [
            ChoicesPrediction(values=["cat"], confidences=[0.92])
            for p in paths
        ]

    def save(self, path: Path) -> None:
        torch.save({"model": self.model.state_dict(), "classes": self.classes}, path)

    def load(self, path: Path) -> None:
        checkpoint = torch.load(path, weights_only=True)
        self.model.load_state_dict(checkpoint["model"])
        self.classes = checkpoint["classes"]
```

Models always receive absolute file paths — an image model opens them as pictures, a text model reads them as documents — while the dataset keeps them relative.

### Rounds build on each other

`train` continues from the latest checkpoint rather than restarting: the loaded weights are kept, and only the optimiser and schedule are new each round. Adding a class grows the classifier head — existing classes keep the rows they learned, the new one starts fresh — so `class add` costs nothing in accumulated training. If the class list changes in any way other than appending, the index each neuron stands for would shift, so the model is rebuilt from pretrained weights and says so.

`--fresh` forces that rebuild deliberately. Hyperparameters always come from `[model.params]`; a checkpoint contributes weights and the class list only.

---

## CLI reference

| Command | Description |
|---|---|
| `auto-labeller new <name>` | Scaffold `projects/<name>/` (`--class`, repeatable; `--single`, `--template`) |
| `auto-labeller templates` | List the available label config templates |
| `auto-labeller projects` | List projects with their classes, sample counts and LS project id |
| `auto-labeller init` | Create the Label Studio project, import tasks, record the project id |
| `auto-labeller ingest` | Scan the data root for new images and register them in `dataset.json` |
| `auto-labeller class add <name>` | Add a class to the project and to the Label Studio config |
| `auto-labeller class list` | List classes with sample counts, flagging any not declared |
| `auto-labeller unskip` | Return skipped samples to the review queue (`--limit N`) |
| `auto-labeller train` | Fine-tune the model on labeled data, save checkpoint + round metadata |
| `auto-labeller predict` | Run inference on unlabeled images and print results |
| `auto-labeller push` | Push predictions to Label Studio as pre-annotations, creating tasks on demand |
| `auto-labeller export` | Merge corrected annotations from Label Studio into `dataset.json` |
| `auto-labeller serve` | Start the ML backend server for live predictions inside Label Studio |
| `auto-labeller report` | Print a round summary with delta metrics vs the previous round |

`push` supports `--sample N` (predict on a random subset of the unlabeled pool), `--limit N` (push only the top-N most uncertain), and `--refresh` (replace existing pre-annotations). On large datasets the typical round is:

```bash
uv run auto-labeller push --refresh --limit 1000 --sample 20000
```

Label Studio only ever holds the tasks you have reviewed or are about to review; the full image inventory lives in the dataset JSON, maintained by `ingest`.

Every command accepts `--project/-p`; the ones that talk to Label Studio also accept `--config` for a non-default host `config.toml`.

### Full iteration example

```bash
# Round 1: you have hand-labeled ~50 images in dataset.json already
export AUTO_LABELLER_PROJECT=projects/cats     # or pass -p cats to every command

uv run auto-labeller init                # creates the LS project, records its id
uv run auto-labeller train               # trains round 1, saves checkpoints/round_001.pt
uv run auto-labeller push                # pushes predictions for unlabeled images
                                         # uncertain images appear first in LS

# ... review and correct labels in Label Studio ...

uv run auto-labeller export              # writes corrected labels back to dataset.json

# Round 2
uv run auto-labeller train
uv run auto-labeller push
# ... review ...
uv run auto-labeller export

uv run auto-labeller report              # compare round metrics
```

---

## Adding a class mid-project

Classes rarely survive first contact with the data — a bunny turns up while you are labelling cats and dogs. Adding one takes a single command:

```bash
uv run auto-labeller class add bunny
```

It appends the class to `project.toml` and inserts a `<Choice>` into the project's *live* Label Studio config, assigning the next hotkey. The config is edited in place rather than regenerated, so a layout you tuned in the LS UI survives untouched. Refresh the tab and the new option is there; existing tasks, annotations and predictions are unaffected.

Two rules make this safe:

- **Classes are append-only.** A checkpoint maps output neurons to the class list by position, so new classes go on the end and never reorder existing ones. If `classes` was empty and being inferred from the data, `class add` pins the inferred order first.
- **Undeclared labels are reported.** If you add the class in the Label Studio UI instead, `export` warns that the label exists in the data but not in `project.toml` — where it would otherwise train as nothing, since the model's head is built from the declared list.

### Skipped images are where the new class hides

Skipping is the natural response to an image whose content has no class yet, and skipped samples are excluded from both training and the review queue. After adding the class, bring them back:

```bash
uv run auto-labeller unskip --limit 200
uv run auto-labeller push
```

`unskip` clears the cancelled annotation in Label Studio (which is what a skip is) and returns the samples to the unlabeled pool, so the next `push` queues them with fresh predictions.

---

## Active learning

When you run `push`, predictions are sorted by uncertainty so the most ambiguous images appear at the top of the Label Studio review queue. Annotation effort concentrates where the model is most likely to be wrong.

What uncertainty *means* belongs to the schema: classification uses least-confidence (the top predicted class having a low score), while detection ranks boxes sitting near the decision threshold and treats an image with no boxes as maximally uncertain — the model either found nothing or missed everything, and only a human settles which.

Pass `--no-prioritize-uncertain` to push in dataset order instead.

---

## Round bookkeeping

Each `train` run writes a `rounds/round_NNN/` directory inside the project:

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
  "checkpoint": "checkpoints/round_001.pt"
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

---
