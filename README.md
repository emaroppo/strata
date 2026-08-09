# auto-labeller

A semi-automatic labelling pipeline that closes the loop between model training and human review, on top of a durable catalog of samples and annotations. Instead of labelling thousands of samples by hand, you label a small seed set, train a model, let it pre-label the rest, then only correct what it got wrong. Each round the model improves and there is less to fix.

Images and text documents are both supported, for whole-sample classification, bounding boxes, or character spans — a project declares which, and everything else follows from that.

It runs on one machine with nothing installed but Python, and scales out to a catalog on one host, object storage on another and a GPU on a third, without a consumer noticing the difference.

---

## How it works

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│  Hand-label a   │────▶│  Train a model   │────▶│  Push predictions    │
│  seed set       │     │  on a frozen     │     │  to Label Studio     │
│                 │     │  dataset version │     │  as pre-annotations  │
└─────────────────┘     └──────────────────┘     └──────────────────────┘
        ▲                                                    │
        │                                                    ▼
        │        export corrected labels           ┌──────────────────────┐
        └──────────── to the catalog ──────────────│  Review & correct in │
                                                   │  Label Studio        │
                                                   └──────────────────────┘
```

**Each round:**

1. `ingest` registers files in the catalog — content-addressed, so re-running over a growing directory is safe
2. `push` runs inference over everything unreviewed and sends the least confident to Label Studio, with the model's guess attached
3. You review in Label Studio: confirm what is right, fix what is not
4. `export` pulls the corrections back into the catalog
5. `train` freezes a dataset version, materialises it, and fine-tunes from it
6. Repeat

The catalog is the durable asset. Everything else is a producer or a consumer of it — annotations outlive the tool that collected them.

---

## The catalog

Samples, what is known about them, and the datasets built from them.

**Samples are addressed by content.** A sample's identity is the sha256 of its bytes, so ingesting the same file twice under two names is one sample, and a reference written today still resolves after the bytes have moved from a directory into a tar in a bucket.

**Collections say where data came from** — `sat_images`, or `sat_images/2024` for one batch. A project names which collections it draws from, so one catalog serves several jobs without their review queues bleeding into each other. Dropping a collection from a project declares that data out of scope, training included.

**A label set is a schema plus the annotations against it.** Unlabelled is the absence of a row rather than a flag, so there is no combination of states that means nothing. A reviewer who looked and found none of the classes present has *answered* — that is a real annotation, and distinct from a sample nobody has seen.

**A dataset version is frozen and materialised.** `train` selects the labelled samples, assigns a train/val split, and writes a self-contained directory: files named by checksum, plus a manifest carrying annotations, split and grouping. The model gets a directory and nothing else — no database, no catalog, no network. That is what makes a run resolve back to the exact samples behind it.

Two properties of the split are load-bearing:

- **Groups are indivisible.** Video frames sharing a `group_id` never straddle train and val, because near-duplicates on both sides make a validation score meaningless.
- **Membership is inherited.** A sample in val stays in val in the next version, so a warm-started model is never scored on what it has already trained on.

### Storage and index are separate axes

| | local | shared |
|---|---|---|
| **index** | SQLite beside the blobs | Postgres |
| **blobs** | a directory of files | tar shards in S3-compatible storage |

The local pair needs no infrastructure, which is what keeps a fresh clone runnable. The schema and the queries are identical either way.

Blobs are packed into tars rather than stored one object each: at a few hundred thousand samples the per-object overhead and the cost of ever listing them are what make per-file storage the wrong shape. The catalog's `(location, offset, length)` is the index, and because a tar member's bytes are contiguous, one sample is one HTTP range request.

---

## Projects

A **project** is a directory holding everything belonging to one labelling job — label schema, which collections it draws from, its model, and its runs. The tool is the machine; the catalog is the asset; the project is the work.

```
projects/
└── my-project/
    ├── project.toml        # label schema, collections, model, LS project id
    ├── model.py            # optional: a model this project carries
    ├── datasets/           # materialised dataset versions
    ├── runs/               # runs, metrics and checkpoints
    └── data/raw/           # files waiting to be ingested
```

```toml
[label_config]
classes = ["cat", "dog"]

[catalog]
# Which collections this job draws from. Defaults to one named after the
# label set.
collections = ["my_images"]

[model]
ref = "multilabel"          # a registered name, or model.py:MyModel

[model.params]
num_epochs = 4

[model.fresh_params]        # applied on a cold start, which needs longer
num_epochs = 10
```

---

## Setup

### One machine

**1. Install**

```bash
uv sync --extra image        # or --extra text, or --extra all
```

The base install carries no ML framework — only the pipeline, which needs nothing heavier than the Label Studio SDK. Torch comes with the extra for the media you are labelling, because exactly one thing needs it: the baseline models. A project pointing `[model] ref` at its own `model.py` can stay on the base install and bring whatever framework it likes.

| Extra | Pulls in | For |
|---|---|---|
| `image` | torch, torchvision, timm, Pillow | the image baselines |
| `text` | torch, transformers | the text baselines |
| `postgres` | psycopg | a shared index |
| `s3` | boto3 | blobs in a bucket |
| `serve` | fastapi, uvicorn | the blob server |
| `service` | fastapi, uvicorn, catalog | training over HTTP |

Asking for a baseline whose extra is not installed fails at `train` time with a message naming the extra, not a stray `ModuleNotFoundError`.

**2. Start Label Studio**

```bash
docker compose up -d
```

Available at `http://localhost:8080`. Create an account, then take an API token from Account & Settings → Access Token.

**3. Configure this machine**

Copy `config.example.toml` to `config.toml` (gitignored). It holds *where things are* — nothing about a labelling job, which lives in its project:

```toml
[label_studio]
url = "http://localhost:8080"

[catalog]
root = "catalog"            # SQLite index and blobs, if nothing else is set
```

Credentials come from the environment rather than this file: `LABEL_STUDIO_API_KEY`, and for a distributed setup `PGPASSWORD`, `STRATA_S3_ACCESS_KEY`, `STRATA_S3_SECRET_KEY`, `STRATA_BLOB_SECRET`, `STRATA_MODELLING_TOKEN`. How they get there is your business — a password manager, a systemd `EnvironmentFile`, a sourced script. The tool only ever reads exported variables.

**4. Make a project and start**

```bash
uv run auto-labeller new cats --class cat --class dog
cp -r /path/to/images/* projects/cats/data/raw/
uv run auto-labeller ingest -p cats
uv run auto-labeller init -p cats        # creates the Label Studio project
```

Then label a seed set, and run `train` → `push` → `export` in a loop.

---

## Deployment

Nothing below changes how the tool is used. The same commands run against a catalog on another machine, blobs in a bucket and a GPU elsewhere.

```
   laptop / desktop                catalog host                 GPU host
  ┌────────────────┐            ┌────────────────┐         ┌────────────────┐
  │ CLI            │──index────▶│ Postgres       │◀──index─│ modelling      │
  │ Label Studio   │            │ blob server    │         │ service        │
  │                │──images───▶│ (signed URLs)  │         │                │
  └────────────────┘            │ object storage │◀─blobs──└────────────────┘
          │                     └────────────────┘                 ▲
          └──────────────── submit a round ───────────────────────-┘
```

**The index** is Postgres. `catalog-copy` moves an existing one into it, preserving primary keys — sample ids are referenced by every annotation, every dataset member and the Label Studio task map, so renumbering would silently repoint every task at a different image.

**Blobs** go into any S3-compatible store (Garage, MinIO, S3). `catalog-repack` packs local files into tar shards and repoints the index, uploading each shard before committing the rows that name it. Nothing local is deleted: those files become a read-through cache, so materialising a dataset version links what the host already has and fetches only the rest.

**Images reach Label Studio over HTTP.** The blob server (`strata-blobs`) turns a checksum into one range read. URLs are signed — an `<img>` tag cannot carry an Authorization header, so the URL *is* the credential, and the signature covers the checksum so a leaked link opens one image rather than the corpus. `relink` moves existing tasks onto it, and re-signs when a queue outlives a signature.

**Training runs where the GPU is.** `strata-modelling` accepts a dataset id, materialises it, trains and records the run. A round is submitted rather than awaited: the call returns a job id, and losing the network, closing the laptop or walking out reaches none of it. `train --job <id>` reattaches.

Deployment files live in `deploy/`, with `bootstrap-env.sh` scripts that generate each host's secrets and refuse to overwrite an existing one.

---

## Repository layout

A `uv` workspace of four packages under a `strata` PEP 420 namespace. The dependency graph is enforced by the build rather than by discipline: `catalog` may not import `labeller`, `modelling` or Label Studio, and `modelling` may import `catalog` only from its service layer.

```
auto-labeller/
├── packages/
│   ├── labels/     strata/labels/      # what an annotation is: values and schemas
│   ├── catalog/    strata/catalog/     # samples, storage, annotations, datasets
│   │                 blobs.py          #   local files, addressed by content
│   │                 s3.py             #   tar shards in a bucket
│   │                 repack.py         #   moving one to the other
│   │                 server.py         #   serving a blob over HTTP
│   │                 signing.py        #   URLs a browser may fetch
│   ├── modelling/  strata/modelling/   # train/predict, runs, and the baselines
│   │                 service.py        #   training asked for from elsewhere
│   │                 conformance.py    #   the contract a plugin must pass
│   └── labeller/   strata/labeller/    # the round loop and Label Studio
│                     adapter.py        #   the Label Studio boundary
│                     remote.py         #   asking another host to train
│                     predictions.py    #   not predicting the same thing twice
├── deploy/                             # per-host deployment
├── docs/                               # architecture and roadmap
├── projects/                           # your labelling projects (payload gitignored)
└── docker-compose.yml                  # the development stack
```

---

## CLI reference

| Command | What it does |
|---|---|
| `new` | Scaffold a project |
| `templates` | List label config templates |
| `projects` | List projects and their counts |
| `class add` / `class list` | Extend or inspect a project's classes |
| `ingest` | Register files from the project's data root |
| `init` | Create the Label Studio project and fill it |
| `push` | Send unreviewed samples, least confident first |
| `export` | Pull corrections back into the catalog |
| `train` | Freeze a version, materialise it, train |
| `report` | Training history, or one run in detail |
| `unskip` | Return skipped samples to the queue |
| `relink` | Repoint tasks at their current image URLs |
| `catalog-stats` | What is in the catalog |
| `catalog-probe` | Prove this host can reach index and blobs |
| `catalog-copy` | Move the index into another database |
| `catalog-repack` | Pack local blobs into a bucket |
| `to-catalog` / `import-rounds` | One-way migrations from the pre-catalog format |

Most take `-p/--project`; all take `--config`. `train --job <id>` reattaches to a round already running elsewhere.

---

## The model

A model implements four methods and knows nothing about where its data came from. It is handed file paths and values — never a catalog, a database or Label Studio — which is what lets it be tested against a directory and run on a machine that has neither.

```python
class MyModel(Model):
    task = "classification"

    def finetune(self, train, classes, val=None, on_epoch=None): ...
    def predict(self, paths): ...
    def save(self, path): ...
    def load(self, path): ...
```

`on_epoch` is optional to call but not to accept: a caller watching a round from another machine cannot otherwise tell minute one from minute nine.

Models are found two ways. A short name resolves through the `strata.models` entry point group, so a request can carry `multilabel` rather than an import path — which matters once the request crosses a wire and the backend, not the caller, decides what it can serve. Anything containing `:` is a direct reference, which keeps the quick-experiment path: drop a `model.py` beside your work and point at it. Direct references are refused over HTTP, and the refusal says so.

A plugin can run the contract against itself:

```python
from strata.modelling.conformance import ModelConformance

class TestMyModel(ModelConformance):
    @pytest.fixture
    def model(self):
        return MyModel()
```

---

## Tests

```bash
uv run pytest
uv run ruff check packages/
```

Most of the suite runs on the base install with no framework. The Postgres tests skip unless a database is reachable, and say why — a skip that blames a missing container when the password changed sends you to look in the wrong place.

---
