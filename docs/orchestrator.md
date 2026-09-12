# The orchestrator — design note

Status: **built and run.** `architecture.md` carries the summary; this is
the design in full, kept because the reasoning behind each decision is
worth more than the decision. It is deliberately narrower than
`proposals.md`, which holds everything that might follow.

## What it is for

Every side project so far has re-typed the same sequence: ingest, freeze a
dataset, train, score the pool, push, review, export, go round again — and
then re-typed it with one parameter changed. An experiment here is that
sequence written down once, with the variation declared, so that running it
is one command, re-running it does nothing that has already been done, and
the record of what ran is what a result is read from.

Three layers, and the orchestrator is the top one:

- **Operations.** One function per command, in the package that owns it:
  the catalog's in `catalog`, training and scoring in `modelling`, the
  Label Studio ones in `labeller`. Each takes a request and returns a
  record. This is the CLI split of `proposals.md` §9, done in the shape
  the orchestrator needs.
- **Front ends** over the operations. The CLI for a person, which parses
  arguments, builds the request, calls the operation and renders the
  record. The two HTTP services are the same idea for the two operations
  that run on another machine. The orchestrator is a third front end,
  driven by a config.
- **The orchestrator's own job**, which is not calling operations but
  deciding the calls: expand a config into stages, hash each stage's
  position, skip what the ledger already holds, run the rest in order,
  record what came back.

The orchestrator does not shell out to the CLI. It calls what the CLI
calls. Driving the CLI would mean parsing tables and reading truncated
ids back out of text.

## The experiment file

A project stays what it is: the durable job — catalog, label set,
collections, label config, model. An experiment is a separate file that
references a project and adds variation. Several experiments per project
is the normal case, which is why it is not a section of `project.toml`.

```toml
# experiment.toml
project = "cats-dogs"          # a project directory, as the CLI resolves it
name = "lr-and-epochs"

[[stage]]
use = "dataset"                # a registered stage name
val_ratio = 0.2
holdout_ratio = 0.1

[[stage]]
use = "materialise"

[[stage]]
use = "split"                  # default: inherit the catalog's sides

[[stage]]
use = "train"
model = "multilabel"
fresh = true                   # every trial cold; see "A grid"
params = { num_epochs = 4, lr = 5e-5 }

[[stage]]
use = "evaluate"
on = "holdout"

[grid]
"train.params.lr" = [1e-5, 5e-5, 1e-4]
"train.params.num_epochs" = [4, 8]
# "split.seed" = [1, 2, 3]     # unlocks the split as a parameter; see "What a run saw"
```

Rules, all of which exist so that the file hashes:

- **TOML is what a person edits; canonical JSON is what is hashed.** The
  canonical form is `strata.common.canonical`, with the rules
  `post-process` and `feature-store` already use and re-declare: sorted
  keys, fixed separators, defaults materialised, sets and NaN refused, a
  schema version inside the payload. The experiment's id is the hash of
  its canonical form.
- **A stage is a registered name and literal arguments.** No conditionals,
  no loops, no templating. Anything that needs logic is a stage, not a
  key. This is the discipline `proposals.md` §3 names as what stops a
  declarative pipeline becoming a bad programming language.
- **A trial is the base file plus overrides**, applied to the payload
  before validation and hashing, the way `post-process` applies `--set`.
  A trial's id is the hash of its effective spec. There is no separate
  trial identity to invent.

## A stage

A function taking a request and a context, returning a record.

- **Requests and records are pydantic models**, JSON-serialisable, with
  unknown keys refused. `TrainRequest`, `PredictRequest` and `Run` are
  already this; the rest are written to match.
- **A record references artefacts by identity** — a run id, a dataset
  version, a task map — and never embeds them. What a stage produced is
  looked up by that identity; the record is small enough to sit in the
  ledger whole.
- **The context is the handles**: the catalog, the run store, the host
  settings. A stage that runs remotely — a round sent to the modelling
  host — decides that from whether the context names a host, and returns
  the same record either way. The host's client lives in `modelling`
  beside the service it speaks to, so the train stage dispatches without
  knowing what a labelling project is. A remote round trains on the sides
  the catalog's version carries: a split drawn locally rewrites a copy of
  the directory, and the host materialises from the catalog, so an
  unlocked split is a local round's instrument for now.
- **A stage declares what it consumes and what it produces**, as resource
  kinds: `samples`, `dataset_version`, `dataset_dir`, `run`, `scores`,
  `metrics`, `tasks`, `annotations`. `train` consumes a `dataset_dir` and
  produces a `run`; `push` consumes `scores`; `split` and `perturb` consume
  and produce a `dataset_dir`, since each rewrites the manifest training
  reads. The chain is validated before the first
  stage runs, walking the declared kinds the way `post-process` walks a
  schema through its stages: `push` before any `train` fails at load,
  naming both, rather than an hour in.
- **Every stage carries a version.** Recorded in the ledger beside the
  spec hash, separately, because a changed implementation under an
  unchanged spec is a different result. Same rule as a transform's
  `version` in `post-process` and a model's here.

**Registry.** A hand-maintained table in the orchestrator, one line per
stage, readable in one place: `"train": strata.modelling.stages.train`.
Not an entry-point group. The rule `post-process` states applies — a
plugin seam is designed at the third implementation — and there is no
third-party stage. The orchestrator imports catalog, modelling and the
labeller regardless. The existing three entry-point groups (sample types,
preparers, models) stay as they are. Promote when someone outside
registers a stage.

**What `run_round` becomes.** Today it is `dataset → materialise → train`
in one function, with the warm-start policy inside it. It becomes those
three stages, and the policy becomes explicit in the file: `fresh = true`,
or `parent = "<run id>"`, or the default of the newest run over the
dataset. The policy was always the caller's; now the caller is written
down.

## What a run saw

Three things decide what a model was actually shown, and none of them is
the corpus: which side each sample was on, whether any label was altered
on the way, and which view of each sample each epoch drew. All three are
recorded per run, in the run store, under one heading — what this run
saw — and are queried the same way afterwards: which samples, which side,
which label, which view.

- **The split.** By default a run reuses the sides the catalog's dataset
  version carries: train, val, and holdout once the catalog assigns one.
  That is what makes trials comparable, and it is what "the same split
  across runs" already means today. One consequence of inheritance: the
  catalog draws a holdout only from samples no earlier version placed, so
  a project whose every sample is already train or val gets an empty one,
  reported as such in the manifest. A study wanting a holdout there
  unlocks the split, and the draw is recorded like any other. The `split` stage exists so the
  default can be unlocked: give it a seed, and it draws its own
  assignment; put `"split.seed"` in the grid, and the split is a
  parameter like any other. Either way the realisation — who landed
  where — is recorded, so an inherited split and a drawn one read the
  same in the ledger, and a later trial that should share a draw names
  the record it inherits from.
- **Perturbations.** An optional `perturb` stage flips the label of a
  chosen fraction of the training side, from a seed or an explicit list,
  and records for each touched sample the original and the perturbed
  value. It writes the manifest training reads; the catalog is never
  written to. A study of mislabelled data is a grid over its fraction,
  read against a holdout it never touched.
- **Augmentation.** `proposals.md` §18: the realised parameters of each
  augmentation, per sample per epoch, recorded by the model through the
  contract addition described there. Not in the first slice.

The mechanism is the same for all three — a draw, written down rather than
a seed relied on — and the reason is the same: a number is only readable
if you can say what produced it, and "which samples was this model shown,
with which labels" is the first thing anyone asks of a surprising one.

## The ledger

Under the project, one directory per experiment, one per trial, one
record per stage:

```
<project>/experiments/
  records/<key>.json         every stage record, by its key, wherever made
  <experiment id>/
    experiment.json          the canonical spec
    <trial id>/
      trial.json             the effective spec, canonical, and the overrides
      01-dataset.json        the trial's copy of each record, under its position
      02-materialise.json
      03-split.json
      04-train.json
      05-evaluate.json
```

- **The key is the prefix hash**: the hash of the canonical spec through
  that stage, every upstream stage included, plus the version of the
  implementation that ran it. Computable from the spec alone, before
  anything runs. A stage whose key has a record is skipped and its record
  is handed downstream as if it had run — and since `records/` is shared,
  two trials that agree through a stage share it, as do two experiments
  over one project. The trial's own directory still holds a copy of every
  record it used, marked reused, so a trial reads whole. This is the rule
  `ensure_materialised` and the prediction cache already apply, extended
  to every stage.
- **One input is not in the key: `project.toml`.** The prefix hashes the
  experiment file, and the project supplies what the file does not say —
  the label set, the collections, the model when a stage names none, the
  feature declarations. A change there changes the request, which the
  record shows, but not the key. Either the project's relevant fields join
  the prefix, or an experiment says everything it depends on; the first
  slice leaves this open and the ledger makes it visible.
- **The project as configured, varied where the file says.** A `train`
  stage's parameters are the project's, the file's `params` override them
  key by key, and a grid key lands on top of both — so a grid over one
  parameter of a model with twelve does not have to restate the other
  eleven. A file naming a model other than the project's starts from
  nothing, since the project's parameters were written for its own.
- **An override at load pins its grid key.** `--set train.params.lr=0.9`
  on a file whose grid varies `lr` gives one trial at 0.9, not a grid
  with the override lost under it.
- **Nothing is ever invalidated.** A changed upstream argument changes
  every prefix hash after it, and those stages run again. A corrected
  annotation changes the dataset's annotation digest, which is in the
  `dataset` stage's record, and the versions numbering carries the rest.
- **A run gains a nullable experiment id**, so a study is a query over the
  run store — what `proposals.md` §11 asks for. The trial is in the
  ledger, not on the run.

**Why skipping is allowed here and not in `post-process`.** Its stages
are pure, so its hash *is* the output's identity and a run is written
fresh every time. Two of ours cannot be: training is not deterministic,
and a person reviewing in Label Studio is not a function. So here the hash
is the *request's* identity and the record is what binds it to an output.
Skipping is a decision about cost — a round is minutes on a GPU and a
review is hours — not a claim that re-running would give the same answer.
The ledger says which it is: a record carries the run id it produced, not
a promise.

## A grid

- **Cartesian product** of the listed values, one trial each, in the order
  listed. Nothing smarter: `proposals.md` §11 says the optimiser is the
  last thing to write, and the grid is enough to produce the first result.
- **Sequential.** One GPU refuses a second job rather than queueing it, and
  that is right.
- **Every trial is fresh, or every trial is pinned to one parent.** Never
  warm-started from the previous trial: results would depend on order and
  each trial would measure its parameters confounded with a parent trained
  under different ones. The file has to say which, and a grid whose
  `train` stage says neither is refused at load.
- **Selection reads validation; the result is reported on a holdout the
  study never sees.** The `dataset` stage takes a `holdout_ratio`, and the
  `evaluate` stage reports on that side. With the split inherited, every
  trial is scored on the same samples; with the split in the grid, the
  holdout is drawn per trial and the study reads across draws.
- **Resuming reads the ledger.** A study interrupted after trial four runs
  trial five; nothing before it runs again.

## What it depends on, and what it does not

- **Package:** `strata.experiment`, distribution `strata-experiment`.
  Depends on `labels`, `common`, `catalog`, `modelling` and `labeller`,
  since a full round needs the Label Studio stages. It is the top of the
  graph; nothing depends on it.
- **The stage contract stays free of anything catalog-shaped.** Requests
  and records are plain models with declared input and output kinds. That
  is what lets a `post-process` run or a feature-store composition be a
  stage later: one adapter each behind an extra, and two more resource
  kinds. Neither is in the first slice.

## What the CLI split delivers

- The catalog's administration commands — stats, probe, copy, merge,
  repack, and the three listings — are data-returning functions in
  `strata.catalog.admin` and the modules they already had, rendered by a
  `strata-catalog` command. `runs-merge` is `strata-runs merge` in
  `modelling`. Six hundred lines left the labeller's CLI, and after the
  split they no longer depend on a package about Label Studio.
  `catalog-check` stays in the labeller: it asks the blob server and the
  modelling host, which are the labeller's own settings to know.
- Both new commands are standard-library argparse with plain and `--json`
  output. Rich tables stay in the labeller; the catalog's install stays as
  thin as it is.
- The loop commands in `auto-labeller` become parse, request, stage,
  render, in that order, with `--json` at the top level.
- The duplication findings are the map: the exit tails and the progress
  blocks are already helpers, and what remains — the command preambles,
  the file-admission sequence — is absorbed by the request layer rather
  than fixed in place.

## The first slice

One experiment file, a grid over one baseline's own parameters, on one
real project, the split inherited, scored on a holdout, sequential,
resumable. Its output is the
comparison the review said was missing — rounds against labels reviewed
against a metric — and it is honest without the evaluation package: a
model's self-reported metric is safe to compare while one model is in
play, as `proposals.md` §10 says. Comparing across models waits for
canonical evaluation, which stays where the sequence puts it.

Two things the slice forces forward, both small:

- **The catalog assigns a holdout.** The manifest format has allowed a
  third side since the format was pinned; nothing assigns it. `assign`
  draws holdout before val and inherits it across versions the same way,
  group-aware; `create_dataset` takes a `holdout_ratio` defaulting to
  zero; the dataset table records the asked and achieved figures beside
  val's. One migration, and nothing existing changes.
- **An `evaluate` stage.** The only metric today is the one a model
  reports about itself on val, inside `finetune`; nothing computes one on
  a holdout. `evaluate` predicts over one side — through the prediction
  cache, so a scored sample is never scored twice, and on the host when
  there is one — and scores it against the manifest's values by one
  implementation: exact-set match and micro precision, recall and F1 over
  the classes asserted, plus the same three per class. Neither is called
  accuracy: a label set carrying two classes per sample scored by a model
  that asserts one has an exact match of zero and a precision worth
  reading, which the plant project showed on its first run. Classification only; spans and boxes are
  refused rather than approximated. It is the first piece of the
  canonical evaluation `proposals.md` §10 describes, pulled forward
  because the slice cannot be read without it. Comparing across models
  still waits for the rest.

Order of work:

1. `strata.common.canonical`, with a contract test against a payload
   hashed by `post-process`'s implementation.
2. The catalog holdout: `assign`, `create_dataset`, the migration, the
   manifest writer.
3. Request and record types, and the stage functions, for the stages the
   slice needs: `dataset`, `materialise`, `split`, `train`, `evaluate`.
   `run_round` and the `train` command call them. Scoring the unlabelled
   pool stays with `push` for now; `evaluate` scores a side of a
   directory itself, through the prediction cache, so a `predict` stage
   is not needed by the slice.
4. The catalog administration commands move, as their own commit.
5. The experiment file, chain validation, the ledger, the grid, and the
   split record. Built: `strata-experiment check|run`, `packages/experiment`.
   The nullable experiment id on `run` is not yet added; the ledger maps a
   trial to its run id, which is enough to read a study until it is.
6. The slice run, and its numbers into the README.

## Not decided

- The package name. `experiment` is closest to how the intent was said;
  `pipeline` is kept free for processing.
- Whether `push` and `export` are stages in the first slice or only
  later. A study that stops at `predict` needs neither; a full round does.
- Whether the ledger records are files or a table. Files first: they are
  read by a person as often as by code, and a table can index them later.
  Built as files.
- Whether the split and perturbation records live in the run store beside
  the augmentation ones, as above, or in the ledger beside the stage that
  made them. The run store, on the argument that all three describe what
  one run saw and are asked about together; the ledger already points at
  the run.
