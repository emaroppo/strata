# strata

Personal infrastructure for small specialised-model projects. A catalog of
samples and annotations that outlives any one project; a labelling loop
with Label Studio that grows it; and an experiment file that runs a study
over it, the sequence written down once, the variation declared, every
stage recorded so nothing is run twice.

It exists because every side project re-typed the same steps, ingest,
freeze a dataset, train, score, review, again, and then re-typed them with
one parameter changed. Here a processing step is written once, as a stage,
and a project is a file that names the ones it uses.

## An experiment is a file

```toml
project = "cats-dogs"          # a project directory: catalog, label set, model

[[stage]]
use = "dataset"                # freeze what is labelled into a version
val_ratio = 0.2
holdout_ratio = 0.1            # kept back; nothing below trains or selects on it

[[stage]]
use = "materialise"            # the version on disk, files by checksum

[[stage]]
use = "split"                  # the version's sides, or a drawn split when unlocked

[[stage]]
use = "train"
fresh = true                   # every trial cold, so they compare

[[stage]]
use = "evaluate"
on = "holdout"                 # one implementation of the score, for every model

[grid]
"train.params.lr" = [0.003, 0.001, 0.0003]
```

```bash
uv run strata-experiment check experiment.toml    # validate, list the trials
uv run strata-experiment run   experiment.toml    # run them, in order, resumably
```

Three things make it reproducible rather than merely repeatable. The
file's canonical JSON is its identity, and each trial's is the file with
its overrides written in. Every stage is a function taking a request and
returning a record that names what it made — a dataset version, a run — and
a ledger under the project keeps each record by the hash of everything
upstream of it. So a stage already run for that prefix is handed downstream
rather than run again: the three trials above share one dataset and one
split, a rerun after an argument changes reruns only what is downstream of
the change, and a rerun of an unchanged file does nothing. The chain is
checked before the first stage runs; a stage before what it needs, or a
grid whose trials would warm-start from each other, is refused at load.

The stages are the same functions the command line calls one at a time.
*Results* below is what the first study produced.

A semi-automatic labelling loop is where the annotations come from: label a
small seed set, train a model, let it pre-label the rest, then only correct
what it got wrong. Each round the model improves and there is less to fix.

## The components

Nine packages under one `strata` namespace, each installable on its own,
each with a README of its own. The dependency graph is acyclic and
enforced by the build: `labels` and `common` are the leaves, `labeller`
and `experiment` are peers at the top over the job they share, and the
catalog may not import the tool that fills it.

| package | what it is | depends on |
|---|---|---|
| [`strata-labels`](packages/labels/README.md) | what an annotation is: value types, schemas, the manifest a trainer is handed | pydantic |
| [`strata-common`](packages/common/README.md) | migration plumbing, a service bootstrap, an entry-point resolver, the canonical form that gets hashed | nothing |
| [`strata-catalog`](packages/catalog/README.md) | samples, storage, annotations, dataset versions; SQLite and files, or Postgres and a bucket | labels, common |
| [`strata-modelling`](packages/modelling/README.md) | train and predict; model plugins, runs, checkpoints, a prediction cache; the training service | labels, common |
| [`strata-project`](packages/project/README.md) | the job as a file: catalog, collections, label set, model; the host's settings | catalog, modelling |
| [`strata-labeller`](packages/labeller/README.md) | the labelling loop, the review queue, and the Label Studio boundary | project, catalog, modelling |
| [`strata-experiment`](packages/experiment/README.md) | an experiment as a file: stages, a grid, a ledger | project, catalog, modelling |
| [`strata-prepare-email`](packages/prepare-email/README.md) | mail into documents: the email type and two converters | catalog |
| [`strata-prepare-video`](packages/prepare-video/README.md) | video into grouped frames | catalog |

Two sister packages hold the same instrument's other half and are read the
same way: [`strata-feature-store`](packages/feature-store/README.md),
structured data with the same frozen versions, and
[`strata-post-process`](packages/post-process/README.md), the
transformations over it. Each is a repository of its own beside the
others, with its own history and CI.

It runs on one machine with nothing installed but Python, and scales out
to a catalog on one host, object storage on another and a GPU on a third,
without a consumer noticing the difference. Images and text documents are
both supported, for whole-sample classification, bounding boxes or
character spans; a corpus that is not already the shape a catalog holds,
mail or video, is converted first by a preparer. Two limits up front: no
detection baseline ships, so a bbox project brings its own model; and the
shipped span tagger refuses a label set that allows overlapping or
multi-label regions, which the catalog and the review queue otherwise
handle.

## Reading order

- Each package README, in the order of the table above.
- [`docs/architecture.md`](docs/architecture.md): the map, and the rules for releasing the packages separately.
- [`docs/adr/`](docs/adr/README.md): one file per decision, with what goes wrong under the alternative.
- [`docs/orchestrator.md`](docs/orchestrator.md): the experiment file's design in full.
- [`docs/roadmap.md`](docs/roadmap.md): how it was built, and what it cost.

## Setup

```bash
uv sync --extra image        # or --extra text, or --extra all
cp config.example.toml config.toml
docker compose up -d         # a Label Studio for development
```

The base install carries no ML framework. `config.toml` says where things
are on this machine and nothing about a job; credentials come from the
environment. The catalog and labeller READMEs have the rest, and
`deploy/` holds the two hosts' units and compose files.

## Tests

```bash
uv run pytest
uv run ruff check .
```

Each package's tests also pass with only that package installed, and CI
checks it for all eight: every wheel built, the package installed alone,
the others coming from those wheels as they would from an index.

## Results

The first study run through the experiment file above, on the plant
project: the learning rate at three values, ten epochs each from a cold
start, every trial on one frozen dataset version with a tenth of it held
out, and scored on that holdout. Three trials in twenty minutes on one
GPU, with the dataset, its materialisation and the split reused from the
smoke run that preceded it.

| lr | validation accuracy | holdout accuracy | macro F1 on holdout | worst class F1 |
|---|---|---|---|---|
| 0.003 | 0.899 | 0.902 | 0.81 | 0.25 |
| 0.001 | 0.935 | 0.944 | 0.90 | 0.69 |
| 0.0003 | 0.894 | 0.904 | 0.80 | 0.05 |

Validation accuracy is the model's own number, on the side it selected
on. Holdout accuracy is the `evaluate` stage's, on samples no trial
trained or selected on, and it tracks validation within a point at every
setting, which is what a holdout drawn before the study should show. The
macro column is where the reading is: the gap between it and the micro
number is the small classes, and the worst class collapses at both ends of
the grid while the middle holds it.

Two things the table does not show, and the records do. The label set
asserts two classes per sample, and this model is asked for one of them
and told the other as a feature, so the exact-match metric is zero by
construction and the micro numbers above are over the classes the model
predicts. The evaluate stage's per-class table is what made that visible
on the first run, and it is what the study is read from. And three points
on one axis is not a finding about learning rates; it is the instrument
working end to end, with every number above resolving through the ledger
to the run, the checkpoint, the dataset version and the answer digest it
came from.

## Provenance

This is infrastructure I run my own projects on, shaped by the projects it
served; a portfolio piece second. The architecture and every design
decision in `docs/` are mine. Much of the implementation was written with
an AI coding assistant working from those decisions, reviewed and run
against real data on three machines. What a reader should weigh is the
judgment: the contracts between packages, the migration story, the reasons
recorded beside each choice.
