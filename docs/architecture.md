# Architecture — planned direction

Status: **plan, not built.** Everything here is a decision record for a
restructuring that has not started. The shipped tool today is one package
that does all three jobs described below in-process.

---

## The problem with one package

Two axes are tangled together in the current code.

The first is **what a sample is**. Media is modelled as a flat pair —
`image` or `text` — but the real shape is a hierarchy: frames are a kind of
image that arrive in near-duplicate runs, satellite imagery is a kind of
image with more than three bands and a coordinate system, email is a kind of
text with headers and threads. Each subtype wants its own reading, grouping
and preprocessing. That surface will keep growing, and none of it has
anything to do with annotation.

The second is **where a model runs**. Models are imported and executed
in-process, which forces the labelling side to carry an ML framework, ties
training to whichever machine is running the CLI, and makes a model that
became good enough at its job awkward to use for anything else.

Neither axis is about labelling, and both are things worth reusing
elsewhere.

## Three packages

| Package | Owns | Depends on |
| --- | --- | --- |
| `corpus` | what a sample is, how to find it, how to read it, how samples relate | — |
| `modelling` | train and predict over samples and targets; model plugins | `corpus` |
| `labeller` | which sample to ask a human about next; Label Studio plumbing | `corpus`, `modelling` |

The graph is acyclic and each edge points at something more general than
itself.

Two consequences that settle questions the current code keeps re-opening:

- **The train/val split belongs to `corpus`.** Whether two samples are
  near-duplicates is a fact about the corpus, not about the annotation job.
  `modelling` consumes a split; `labeller` asks for one.
- **Decoding belongs to `corpus` too.** `_load_rgb` inside the image
  classifier is why satellite imagery would be painful today: a model that
  hardcodes three channels cannot take an eight-band GeoTIFF. If `corpus`
  owns "read a sample of this subtype into an array", the subtype axis stops
  leaking into model code.

### One repo, not three

A `uv` workspace, which the build already uses everywhere.

This gives the parts of a split that are actually wanted — a `pyproject.toml`
per package, independently declared dependencies, separate extras so that
satellite support does not pull the Label Studio SDK and the labeller does
not pull a raster stack, independent publishability — without the part that
is pure cost: a version-pinning dance on every change that touches two
packages, which during a restructuring is most of them.

`git subtree split` peels a package into its own repo later with history
intact. The expensive part of a split is settling the interface; the repo is
a mechanical step afterwards, and the interface is still moving.

### Subtypes are classes, not entry points

In-tree classes with extras for the heavy dependencies. Entry-point
discovery only once something out-of-tree needs to register, which is the
same bar that was applied to model plugins and not yet met for media.

## Two containers

Not three. One of the three boundaries is a data plane and does not want a
network in it.

```
┌───────────────┐     HTTP      ┌──────────────┐
│   labeller    │──────────────▶│  modelling   │
│  + Label      │               │  (GPU host)  │
│    Studio     │               │              │
└───────┬───────┘               └──────┬───────┘
        │                              │
        │      both import corpus      │
        └──────────────┬───────────────┘
                       ▼
             shared storage (volume or object store)
```

**`labeller` ↔ `modelling` over HTTP.** Training is long-running, so it
wants to be a submitted job rather than a blocking call. The framework image
is multi-GB while the labelling image is small. And the payoff is locality:
`modelling` runs where the GPU is, labelling happens from anywhere, and a
model that got good enough serves other work without dragging an annotation
tool along. `ls_backend.py` is already a FastAPI service that loads a
project's model and serves predictions — the modelling container is that
generalised from predict-only to predict-and-train.

**`corpus` is a library, not a service.** Training reads the bytes of every
sample several times per epoch. HTTP in that path turns a page-cache read
into a round trip inside the inner loop. Both containers import `corpus` and
both see the same storage. If storage should be owned properly, the
container to add is MinIO or S3 and `corpus` is the client on top of it:
object storage in the byte path, Python in the metadata path.

A catalogue API over `corpus` — what samples exist, their subtypes, their
groups, their split — is a possible later addition. Small payloads, low
frequency, and separable from the bytes.

### What makes this cheap here

- `dataset.json` already stores **data-root-relative** paths, which is the
  thing that usually breaks containerised training.
- The mount-agreement problem is already solved once:
  `[label_studio] local_files_root` and `local_files_prefix` exist because
  Label Studio is a container that has to see the files at an agreed path.
  `modelling` is the same pattern a second time.
- `docker-compose.yml` already has the bind-mount idiom worked out.

## The request is the contract

`modelling` is a library with an HTTP adapter, never HTTP-only. `labeller`
builds a request object and hands it to either the in-process handler or an
HTTP client.

The in-process path **calls the same handler** rather than bypassing it. So
validation is one code path, error text is identical local and remote, and
the failure mode where it works on a laptop and 400s against the GPU host
cannot arise. `pytest` needs no containers, and the boundary cannot rot
because both sides of it stay exercised.

A train request carries: model name, model params, schema type, class list,
and the samples with their targets and split assignment.

### The backend is the only authority on what it can serve

No capability negotiation. A fetched capability list can be stale by the
time a job is submitted, so the request-time check is needed regardless, and
building both makes the list a cache that can only ever be wrong.

That pulls the schema check across too. `run_training` currently compares
`model.schema_type` against the project's schema in-process; with the schema
type in the request, the backend validates "plugin installed, and it handles
this schema type" in one place, on the side that has the facts.

Two things this demands:

- Params must come back as a **structured error naming the parameter**. In
  process a bad param is a `TypeError` from `model_cls(**params)`, which
  reads fine in a terminal; over the wire that is a 500 with a traceback.
- An `auto-labeller models` command that proxies the backend's list. Not for
  validation — for the fact that nothing otherwise checks `project.toml`
  until a train, which in this tool can be after labelling a few hundred
  samples.

## Where a model comes from

Machine-level and job-level settings stay separated the way `config.py`
already states: *how this host reaches things* in `config.toml`, *what this
job is* in the project directory.

```toml
# config.toml — this machine
[modelling]
url = "http://gpu-host:8000"    # omit to run in-process

# project.toml — this job
[model]
name = "presence-classifier"    # a plugin the backend has installed
version = "2"

[model.params]
num_epochs = 4
```

The endpoint must not live in `project.toml`. If it did, one endpoint would
mean one model, a project could not move between a laptop and the GPU host
without an edit, and a backend could not serve several projects — which was
the reason to have a backend.

**Entry points are now justified for models.** They were rejected earlier,
correctly, because every "plugin" shipped in the same repo. With a backend
that stops being true: a plugin becomes an installable package someone else
can publish and an operator installs into the backend image.

**`ref = "model.py:Class"` survives for in-process mode.** The casual path
today is "drop a `model.py` in the project and go"; requiring a package and
an image rebuild for a quick experiment is a real regression. There is no
container boundary in-process, so nothing forces giving it up. Named plugins
are how the remote backend works, and the config makes plain which mode is
in play.

### The cost, recorded deliberately

`project.py` promises a project directory is "a self-contained, portable
labelling job". Once the model is a plugin on a server, handing someone that
directory gives them annotations and checkpoints but not the model that
produced them.

That is an acceptable trade, but it is a downgrade and should be written
down rather than quietly stop being true:

- Record model **name and version** in `rounds/*/metadata.json`, so a
  handoff is reproducible given a backend that has the plugin.
- **Refuse a checkpoint whose recorded version does not match** what the
  backend now serves. This matters more than it looks: checkpoints map
  output neurons to the class list *by position*, which is why `add_classes`
  is append-only. Today the model code sits inside the project and cannot
  change underneath it. With a remote backend, a plugin upgrade between
  rounds silently invalidates the mapping.
- Update that docstring when the change lands.

## Two open problems this restructuring absorbs

**A. Mixed corpora.** A project cannot hold both standalone images and video
frames — `[data] kind` is one value for the whole project. Under `corpus`
this becomes a question of where group keys come from rather than a question
about the split, because the split will always group and a standalone sample
is a group of one. The likely shape:

```toml
[data]
kind = "images"
frame_dirs = ["clips/*"]   # these subtrees are frame runs
```

**B. Validation membership is not stable.** Which samples are validation is
recomputed on every train — shuffle, take the last fraction. Labelling more
samples changes the shuffle, so samples move between the two sides. Because
rounds warm-start from the previous checkpoint, a sample that moves into
validation is then scored by a model that already trained on it, and the
number flatters itself.

The fix is to persist the decision instead of deriving it. A `val` flag per
sample in `dataset.json`, tri-state so that undecided is distinguishable
from decided-as-train, assigned once and never revisited:

- Round 1, 50 labelled: 40 get `false`, 10 get `true`, written out.
- Round 2, 50 more labelled: the original 50 keep their flags. Target is 20
  of 100; 10 already exist; so 10 of the new samples get `true`.

Assignment aims at the deficit rather than flipping a coin per sample, so a
ratio knocked off target by an earlier round is corrected by the next one.
Groups are taken into validation only while doing so lands closer to the
target than skipping them, which caps overshoot at half a group. A group
found straddling both sides is forced wholly to train — the only case where
a decided sample is overruled, and the direction that removes the leak
rather than preserving it. An outcome with an empty side is an error, not a
warning: one video under `kind = "frames"` cannot produce a held-out video,
and saying so beats reporting a meaningless score.

Note `Sample.val` and its `dataset.json` round trip exist in the working
tree already; the assignment logic does not.

## Order of work

1. **`corpus`** — depends on nothing, and both open problems above live in
   it. The subtype hierarchy gets designed here.
2. **`modelling`** — largely a move of `models/`, `model.py`, `train.py` and
   `predict.py`, plus lifting decode out into `corpus`. In-process
   implementation and the request types first; the HTTP adapter once the
   interface stops moving.
3. **`labeller`** — what remains.
4. **Containers** — the compose stack falls out of step 2 and doubles as the
   runnable demo the README needs.

The interface is designed first and the containers ship last, so the wire
format is not retrofitted onto an interface that grew in-process.

### Honest cost

This is more work than everything left on the pre-existing TODO combined,
and it pushes publishing out. It is a defensible trade for a tool meant to
be used rather than only shown, but it should be a decision rather than a
drift.
