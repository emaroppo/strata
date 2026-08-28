# auto-labeller

A semi-automatic labelling pipeline that closes the loop between model training and human review, on top of a durable catalog of samples and annotations. Instead of labelling thousands of samples by hand, you label a small seed set, train a model, let it pre-label the rest, then only correct what it got wrong. Each round the model improves and there is less to fix.

Images and text documents are both supported, for whole-sample classification, bounding boxes, or character spans — a project declares which, and everything else follows from that. A corpus that is not already the shape a catalog holds — mail, video — is converted first by a `prepare` step, which is a plugin surface of its own.

Two limits worth stating up front. Boxes can be labelled, stored, exported and merged, but no detection baseline ships yet, so a bbox project cannot be trained without bringing its own model. And spans may overlap or carry several labels each where the label set declares it — that reaches the catalog, the review queue and an export, but the shipped tagger refuses to train on it, because BIO tagging gives each token exactly one tag.

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

0. `prepare` converts a corpus into what the catalog holds, when it did not arrive that way — mail into documents, video into frames. Skipped entirely for a directory of images
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

**A sample has a type, and types inherit.** `image`, `text`, `frames` are
built in; a plugin adds `satellite` by subclassing `Image`, or `email` by
subclassing `Text`, and everything that accepts the parent accepts it. A
type declares the extensions it admits (checked, not used to discover), what
metadata to read off a file, how samples group, and what canonical form its
bytes are stored in. Subtypes are a path — `satellite/multispectral` — so
asking for `satellite` matches what it grew into without knowing the name. A
subtype cannot change its media, because a query for images would then
silently stop returning it.

**Text is stored one way.** UTF-8, LF endings, NFC, no BOM — applied at
ingest, so two documents that read identically are one sample rather than
two. For anything annotated by character offset that is not tidiness: a
browser normalises line endings on its own, so a document ingested with
CRLF hands a reviewer different offsets from the ones a tokenizer will see,
and nothing raises. Encoding is refused rather than guessed, because a
mojibake document ingests, renders as something plausible, and is annotated
against characters that were never there.

The line this does not cross is normalisation — consistent column names,
key ordering, whitespace someone prefers. The test is whether two
independent implementations would produce identical bytes. Anything that
encodes a preference would make a checksum depend on our own release, and
`catalog-merge` matches samples on checksum precisely so that two hosts on
different releases still agree about what a sample is.

**Collections say where data came from** — `sat_images`, or `sat_images/2024` for one batch. A project names which collections it draws from, so one catalog serves several jobs without their review queues bleeding into each other. Dropping a collection from a project declares that data out of scope, training included.

**A label set is a schema plus the annotations against it.** Unlabelled is the absence of a row rather than a flag, so there is no combination of states that means nothing. A reviewer who looked and found none of the classes present has *answered* — that is a real annotation, and distinct from a sample nobody has seen.

**Nothing carries a sample id without saying which catalog issued it.** A
run records its catalog, a materialised dataset records it in the manifest,
a round is refused by a host serving a different one, and the Label Studio
task map — a `{sample_id: task_id}` cache — records it and refuses to be
read against another. That last one is the sharp edge: every id in a map
exists in both catalogs and names a different sample, so `push` would
attach predictions to the wrong images and `unskip` would delete answers on
unrelated tasks, with nothing raised anywhere.

**A host can hold several catalogs.** `config.toml` names them —
`[catalog.images]`, `[catalog.text]` — with the host's own settings stated
once above them and each table layering on top. A project says which it
draws from; commands with no project take `--catalog`. A name that matches
nothing is refused rather than falling back, because a sample id means
nothing outside the catalog that issued it: opening the wrong one reports
real numbers about the wrong data.

**A catalog has an identity**, minted once and carried by any copy of it.
A sample id, a dataset name and a collection all mean something only within
one catalog, and nothing said which until this existed. It is what lets a
laptop take a copy, work offline, and have its answers folded back.

**Disagreement is recorded, not resolved.** When a merge finds two answers
for the same sample, the catalog keeps the one it had and remembers the
other. Choosing between them is exactly what it cannot do — both were made
by someone looking at the sample — so `push` sends disputed samples to the
front of the review queue and a person settles it. Answering again clears
it, whichever way they go.

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

## Getting a corpus in

Almost no corpus arrives as the thing a catalog holds. Mail arrives as `.eml` or as a blob of message JSON; frames arrive as video. A **preparer** converts one into the other, and `ingest` catalogues the result:

```bash
uv run auto-labeller prepare -p my-project    # data/source → data/raw
uv run auto-labeller ingest  -p my-project
```

Two steps rather than one, because ingest is where content addressing, grouping and collections are decided, and a converter reaching around it would be a second implementation of the thing most worth having only one of. The source directory is kept: one holds the corpus as it arrived, the other as the catalog stores it, and a conversion that overwrote the first would be a one-way door.

Alongside the files, a conversion writes `prepared.json` — what it knew that a filename cannot hold. Two things come out of it. **Metadata**: a sender, a subject, a frame's index in its video. And **grouping**: what extracted a video's frames knows they are one video, where a sample type could only infer it from a directory layout both sides have to agree about. A corpus that arrived already labelled carries its candidate annotations there too — a regex's guesses or another model's — and nothing lands them in the catalog on its own.

| Preparer | Reads | Produces | Ships in |
|---|---|---|---|
| `eml` | `.eml` | `email` documents | `strata-prepare-email` |
| `email-json` | `.json` | `email` documents | `strata-prepare-email` |
| `video-frames` | `.mp4`, `.mov`, `.mkv`, … | `frames` | `strata-prepare-video` |

`preparers` lists what is installed. Which one runs is resolved from the pair — what the files are, and what the project ingests — since `.json` is a mailbox to one converter and something else entirely to another; an ambiguity is refused with both names rather than settled by install order.

A conversion promises four things, checked by `PreparerContract`: its output is admitted by the type it claims to produce, that output is already in that type's canonical form, it reports what it did not carry across, and the same input twice gives the same bytes. The last is the load-bearing one. A corpus that comes out different on a second run re-checksums, and re-checksumming a corpus somebody has already annotated does not lose the annotations — it silently detaches them.

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
    ├── data/source/        # a corpus waiting to be converted, if it needs it
    └── data/raw/           # files waiting to be ingested
```

```toml
[label_config]
classes = ["cat", "dog"]
# Span projects only, and both default to off. They say what the job is
# rather than what is preferred: a model that cannot represent either
# refuses the label set instead of training on a projection of it.
# multi_label = true     # one region may carry several labels
# overlapping = true     # two regions may intersect

[data]
# A registered sample type. Decides which files ingest admits, what canonical
# form they are stored in, and how they group — 'frames' groups by the folder
# they sit in. `types` lists what is installed.
type = "image"
# Only for a corpus that needs converting first. `preparers` lists what is
# installed; naming one is optional, and settles an ambiguity.
# source_root = "data/source"
# preparer = "eml"

[catalog]
# Which catalog on this host. Empty means the host's default, which is the
# only one on a host with one.
name = "images"
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

Converters are separate distributions rather than extras, because each carries a parser or a decoder that most installs have no use for: `strata-prepare-email` needs nothing beyond the standard library's mail parser, `strata-prepare-video` carries OpenCV. A checkout of this workspace installs every member including those two; what the separation buys is that nothing in the catalog imports them, and that a deployment or a downstream install of the labeller carries neither.

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

A host with more than one corpus names them instead — `[catalog.images]`,
`[catalog.text]` — and the keys above them stay the host's, so a shared
bucket is stated once. `auto-labeller catalogs` lists what is configured
and asks each one for its identity, which is how two names accidentally
pointing at one database become visible.

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

**Samples reach Label Studio over HTTP.** The blob server (`strata-blobs`) turns a checksum into one range read — an image to display, a document to fetch. URLs are signed: a browser loading a sample cannot carry an Authorization header, so the URL *is* the credential, and the signature covers the checksum so a leaked link opens one sample rather than the corpus. Text is served with its encoding stated, which after the canonical form is a fact rather than a guess. `relink` moves existing tasks onto the server, and re-signs when a queue outlives a signature.

**Training runs where the GPU is.** `strata-modelling` accepts a dataset id, materialises it, trains and records the run. A round is submitted rather than awaited: the call returns a job id, and losing the network, closing the laptop or walking out reaches none of it. `train --job <id>` reattaches.

**Work can happen away from the index.** `catalog-copy` takes a copy,
`catalog-merge` folds its answers back — copying what the main catalog
lacks, staying silent where both agree, and recording a conflict where they
disagree. `runs-merge` does the same for a training history split across two
machines. Both report what they would do and write nothing until `--apply`.

Deployment files live in `deploy/`, with `bootstrap-env.sh` scripts that generate each host's secrets and refuse to overwrite an existing one.

---

## Repository layout

A `uv` workspace of four packages under a `strata` PEP 420 namespace, plus two optional converter plugins. The dependency graph is enforced by the build rather than by discipline: `catalog` may not import `labeller`, `modelling` or Label Studio, and `modelling` may import `catalog` only from its service layer.

```
auto-labeller/
├── packages/
│   ├── labels/     strata/labels/      # what an annotation is: values and schemas
│   ├── catalog/    strata/catalog/     # samples, storage, annotations, datasets
│   │                 sample_types.py   #   what a sample is, and what admits it
│   │                 builtin_types.py  #   image, text, frames
│   │                 preparers.py      #   turning a corpus into one of those
│   │                 prepared.py       #   what a conversion knew, per sample
│   │                 merge.py          #   folding a copy's answers back
│   │                 blobs.py          #   local files, addressed by content
│   │                 s3.py             #   tar shards in a bucket
│   │                 repack.py         #   moving one to the other
│   │                 server.py         #   serving a blob over HTTP
│   │                 signing.py        #   URLs a browser may fetch
│   ├── modelling/  strata/modelling/   # train/predict, runs, and the baselines
│   │                 service.py        #   training asked for from elsewhere
│   │                 merge.py          #   joining two histories
│   │                 conformance.py    #   the contract a plugin must pass
│   ├── labeller/   strata/labeller/    # the round loop and Label Studio
│   │                 adapter.py        #   the Label Studio boundary
│   │                 remote.py         #   asking another host to train
│   │                 predictions.py    #   not predicting the same thing twice
│   ├── prepare-email/                  # plugin: the email type, .eml and JSON
│   └── prepare-video/                  # plugin: video into frames (OpenCV)
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
| `prepare` | Convert a corpus into what this project ingests |
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
| `catalog-merge` | Fold a copy's annotations back in |
| `catalog-repack` | Pack local blobs into a bucket |
| `runs-merge` | Fold another run store into this project's |
| `types` | List the installed sample types |
| `preparers` | List the installed conversions |
| `catalogs` | List this host's catalogs and their identities |
| `import-rounds` | One-way migration from the pre-catalog format |

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

A model may also refuse a label set it cannot represent, through `requires_schema`. `task` already catches a classifier pointed at spans; this catches the finer case of the right task and the wrong *shape*. The span tagger declines a label set allowing overlapping or multi-label regions, because BIO tagging gives each token one tag; the two text classifiers decline each other's, because a sigmoid head cannot promise to name only one class and a softmax head cannot name two. Refused before the round rather than during it, since the alternative is training on a projection of the data and reporting a number for the projection.

### The baselines that ship

| `[model] ref` | Task | Media | Notes |
|---|---|---|---|
| `multilabel` | classification | image | several classes at once |
| `multiclass` | classification | image | mutually exclusive |
| `presence` | classification | image | carries an implicit negative class |
| `text` | classification | text | several classes at once, sigmoid |
| `text-multiclass` | classification | text | mutually exclusive, softmax |
| `text-span` | span | text | BIO tagging over tokens |

The pairs differ by four hooks — the loss, the target encoding, the decoding and, for text, how several windows of one document become one answer. Everything else is shared, which is the point of the split: a variant is a handful of overrides rather than a second model.

Nothing ships for boxes. A bbox project can be labelled, stored and exported, but needs its own model to train.

Models are found two ways. A short name resolves through the `strata.models` entry point group, so a request can carry `multilabel` rather than an import path — which matters once the request crosses a wire and the backend, not the caller, decides what it can serve. Anything containing `:` is a direct reference, which keeps the quick-experiment path: drop a `model.py` beside your work and point at it. Direct references are refused over HTTP, and the refusal says so.

---

## Extending it

Four things are plugins, all through entry points, and built-in names are
reserved so a plugin cannot quietly redefine one. Each surface looks the
same on purpose — a registry, a `resolve()` that refuses an ambiguity rather
than picking a winner, and a conformance suite — because consistency across
four is worth more than any local improvement to one of them.

| Group | Adds | Extends |
|---|---|---|
| `strata.models` | a model | `Model` |
| `strata.sample_types` | a kind of sample | an existing `SampleType` |
| `strata.preparers` | a way to convert a corpus | `Preparer` |
| — | a kind of annotation | `Value` and `Schema`, in `strata.labels` |

Sample types extend by **inheritance** rather than by replacement: a
`Satellite(Image)` is an image everywhere an image is expected, and cannot
change its media. That is what stops a plugin from making a query for
images stop returning some of them.

Models, label types and preparers each have a conformance suite — a base
class of tests a plugin runs against itself:

```python
from strata.modelling.conformance import ModelContract

class TestMyModel(ModelContract):
    @pytest.fixture
    def model(self):
        return MyModel()
```

`LabelTypeConformance`, in `strata.labeller.conformance`, is the strictest, because a label type has the
furthest to travel: it drives a value through the discriminated unions, the
catalog, a manifest, a materialised dataset, the prediction cache, the wire,
Label Studio and the ranking. Being flexible about label format is a core
objective of this project, and every place that pinned itself to
classification was found by writing that suite rather than by anything
failing.

`PreparerContract`, in `strata.catalog.preparer_conformance`, guards the one
thing here that invents bytes rather than carrying them, which makes it the
one thing whose mistakes cannot be recovered from what is stored.

---

## Tests

```bash
uv run pytest
uv run ruff check packages/
```

Most of the suite runs on the base install with no framework. The Postgres tests skip unless a database is reachable, and say why — a skip that blames a missing container when the password changed sends you to look in the wrong place.

---
