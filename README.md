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
name = "lr-sweep"              # what its trials are listed and recorded under

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

Eight packages under one `strata` namespace, each a repository of its own
with its README, its CI and its history, held here as submodules so one
checkout carries the whole system. The dependency graph is acyclic and
enforced by the build: `common` is the leaf and `contracts` sits on it,
`labeller` and `experiment` are peers at the top over the job they share,
and the catalog and the preparers that fill it never import each other —
what passes between them is a prepared index, defined in `contracts`.

| package | what it is | depends on |
|---|---|---|
| [`strata-contracts`](https://github.com/emaroppo/strata-contracts) | what crosses a boundary: sample types and the prepared index going into a catalog, annotation values and schemas, the manifest a trainer is handed | pydantic, common |
| [`strata-common`](https://github.com/emaroppo/strata-common) | migration plumbing, a service bootstrap, an entry-point resolver, the canonical form that gets hashed | nothing |
| [`strata-catalog`](https://github.com/emaroppo/strata-catalog) | samples, storage, annotations, dataset versions; SQLite and files, or Postgres and a bucket | contracts, common |
| [`strata-prepare`](https://github.com/emaroppo/strata-prepare) | raw data into a prepared corpus: preparers, the folder ones, the conformance suite | contracts, common |
| [`strata-modelling`](https://github.com/emaroppo/strata-modelling) | train and predict; model plugins, runs, checkpoints, a prediction cache; the training service | contracts, common |
| [`strata-project`](https://github.com/emaroppo/strata-project) | the job as a file: catalog, collections, label set, model; the host's settings | catalog, modelling |
| [`strata-labeller`](https://github.com/emaroppo/strata-labeller) | the labelling loop, the review queue, and the Label Studio boundary | project, catalog, prepare, modelling |
| [`strata-experiment`](https://github.com/emaroppo/strata-experiment) | an experiment as a file: stages, a grid, a ledger | project, catalog, modelling |

Plugins are not packages of the system but extensions of one: the
first-party ones live in [`strata-plugins`](https://github.com/emaroppo/strata-plugins),
one distribution per plugin under the package it extends (video into
grouped frames, for `prepare`), and
`strata-prepare-email`, mail into documents, is the emails demo project's
own plugin (`strata-demo-emails`, beside these repositories), an example of
one written outside them.

Two sister packages hold the same instrument's other half and are read the
same way: [`strata-feature-store`](https://github.com/emaroppo/strata-feature-store),
structured data with the same frozen versions, and
[`strata-post-process`](https://github.com/emaroppo/strata-post-process), the
transformations over it. Repositories of their own like the rest, held
here the same way.

It runs on one machine with nothing installed but Python, and scales out
to a catalog on one host, object storage on another and a GPU on a third,
without a consumer noticing the difference. Images and text documents are
both supported, for whole-sample classification, bounding boxes or
character spans. Every corpus is prepared before a catalog takes it: mail
or video is converted by a preparer, and a folder already in shape is
indexed where it sits. Two limits up front: no
detection baseline ships, so a bbox project brings its own model; and the
shipped span tagger refuses a label set that allows overlapping or
multi-label regions, which the catalog and the review queue otherwise
handle.

## Reading order

- Each package README, in the order of the table above.
- [`docs/architecture.md`](docs/architecture.md): the map, and the rules for releasing the packages separately.
- [`docs/adr/`](docs/adr/README.md): one file per decision, with what goes wrong under the alternative.
- [`docs/orchestrator.md`](docs/orchestrator.md): the experiment file's design in full.

## Setup

Needs `git` and [uv](https://docs.astral.sh/uv/), which fetches Python 3.13 itself:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh     # uv, if it is not installed
git clone --recurse-submodules <this repository>
uv sync --extra image        # or --extra text, or --extra all
cp config.example.toml config.toml
docker compose up -d         # a Label Studio for development
```

After a `git pull`, `git submodule update --init` brings each package to
the commit this checkout names. A change to a package is committed and
pushed in `packages/<name>`; this repository then records the new commit
with `git add packages/<name>` and a commit of its own. The base install carries no ML framework.
`config.toml` says where things are on this machine and nothing about a
job; a command reads the one `$STRATA_CONFIG` names, so a project directory
anywhere on the machine uses it. Credentials come from the environment. The
catalog and labeller READMEs have the rest; each host's unit and compose
file is in its package, under `deploy/catalog-host` and
`deploy/modelling-host`; the catalog README's "A catalog host" says how
to set one up from nothing.

## One package on its own

The packages are not on PyPI. Each installs from its repository at a
release tag, and each package's README has the exact line. One rule makes it
longer than a plain `uv add`: uv applies a git source only to a package the
project names directly, so a package's strata dependencies are named beside
it, each with its own source. The catalog, which needs `contracts` and
`common`:

```bash
g=git+https://github.com/emaroppo
uv add "strata-catalog @ $g/strata-catalog@v0.1.0" \
       "strata-contracts @ $g/strata-contracts@v0.1.0" \
       "strata-common @ $g/strata-common@v0.1.0"
uv add "strata-catalog[postgres,s3] @ $g/strata-catalog@v0.1.0"   # extras, once it is there
```

Leave one of them out and uv reports the requirements unsatisfiable, naming
the package it could not find. A plugin sits in a subdirectory of
`strata-plugins`: `$g/strata-plugins@v0.1.0#subdirectory=prepare/prepare-video`.

## Tests

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Each package's own repository checks that its tests pass with only that
package installed, its wheel built and installed alone into a fresh
environment. This workspace's CI checks that the packages agree with each
other: one environment, every suite, every extra, and the types.

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
