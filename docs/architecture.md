# Architecture — planned direction

Status: **largely built.** The four packages exist, the labelling loop runs
end to end on the catalog, and the pre-catalog path has been deleted. What
remains unbuilt is object storage, Postgres, the sample-serving API and the
HTTP split — the sections below say which is which.

Sequencing and what is still owed live in `roadmap.md`.

---

## What the system is for

The durable assets are **a labelled data catalog** and **a model catalog**.
The labelling tool is scaffolding that produces the first one. Anything that
makes the catalog depend on the scaffolding has the relationship backwards.

That principle decides most of what follows.

## Four packages

All four live under a `strata` PEP 420 namespace — `strata.labels`,
`strata.catalog`, `strata.modelling`, `strata.labeller`, distributed as
`strata-labels` and so on. Namespacing rather than four bare top-level names
because `catalog` and `labels` collide with almost anything in a shared
environment, and because a fifth package then costs nothing. Independent
installability is unaffected: this is how `google.cloud.*` works.

Short names are used below for readability.

| Package | Owns | Depends on |
| --- | --- | --- |
| `labels` | what an annotation *is*: value types, schema descriptors, the indexing contract | — |
| `catalog` | samples, storage, grouping, annotations, datasets | `labels` |
| `modelling` | train and predict; model plugins; runs and checkpoints | `catalog`, `labels` |
| `labeller` | active learning, and the Label Studio adapter that feeds it | `catalog`, `modelling`, `labels` |

Acyclic, with `labels` as the leaf.

`labeller` is deliberately thin — active learning plus a UI adapter. The
centre of gravity is the catalog.

### One repo, not four

A `uv` workspace, which the build already uses everywhere. That gives a
`pyproject.toml` per package, independently declared dependencies, separate
extras, and independent publishability — without a version-pinning dance on
every change touching two packages, which during a restructuring is most of
them. `git subtree split` peels a package out later with history intact.

## `labels`

The neutral representation, shared by everything.

**Label Studio's format must not go in it.** What `schemas/` is today is an
LS adapter wearing a schema layer's clothes: `Result` is an LS result dict,
`canonicalize` and `strip_volatile` exist to drop LS's volatile fields,
`label_config()` emits LS XML, `MEDIA_TAGS` parses it. If that becomes
`labels`, the catalog is shaped by a replaceable annotation UI.

So `labels` holds value types, schema descriptors, encode/decode/validate —
and LS's XML and result handling stay in `labeller` as a boundary adapter.

**This reverses a decision that was right at the time.** The README says
`dataset.json` deliberately stores canonicalized Label Studio results, so
predictions and annotations share one format and LS's own conversion tools
work on a handoff. Good, while LS was the centre. As the storage format of a
durable catalog it is a vendor wire format in a permanent record — and
`strip_volatile` is the tell: you already scrub it on the way in.

**The indexing contract.** The catalog cannot index opaque JSON, but it does
not need to understand every task type either. It needs each schema to
answer one question: *which classes does this annotation assert?* That is
`classes_in_use`, which already exists. A new task type implements the
contract and becomes queryable without the catalog changing.

**The rule that keeps it from becoming a monolith with extra steps:** no
I/O, no storage, no SDK, no framework. Pure types and pure functions. Shared
kernels are where coupling hides, so this belongs in the package docstring.

## `catalog`

### Storage: shards in object storage, index in Postgres

Images are packed into tars in S3-compatible object storage (Garage
self-hosted) rather than stored as individual objects — small-object
overhead and listing cost make per-file storage the wrong shape at volume.

Tar has no index, so Postgres records `(shard, offset, length)` per sample.
Tar members are contiguous, so one sample is one HTTP range request. That
gives two access modes, chosen per query by selectivity:

- **Sparse** (labelling, review) → range requests, coalescing adjacent members.
- **Dense** (training) → pull whole shards and stream them.

Two things to get right from the start:

- **Shards are immutable.** You cannot append to a tar in object storage
  without rewriting it. New data means new shards; deletion means a
  tombstone in the index and a compaction pass later.
- **Pack with locality.** Keep a video's frames in one shard, so a shard
  tends to fall on one side of a split and dense reads stay dense.
  100MB–1GB per shard.

### Text is stored differently, queried identically

Text documents are kilobytes. Rather than packing them, put the content in
Postgres directly: no index, no range reads, no serving hop, and full-text
search comes free. Email especially — headers and threads want to be
columns, and thread id is the group id.

The line is content type, not size: binary to object storage, text to the
database, with an escape hatch for genuinely large documents. The storage
layer differs; the query layer must not.

### Schema

```
catalog.sample            id, shard, offset, length, media, subtype,
                          group_id, checksum, metadata JSONB

catalog.label_set         id, name, schema (task type, classes, ...)

catalog.annotation        sample_id, label_set_id, results JSONB,
                          annotated, skipped, source, updated_at
                          PK (sample_id, label_set_id)

catalog.annotation_class  sample_id, label_set_id, class_name
                          -- derived on write via labels' indexing contract

catalog.dataset           id, name, version, query, created_at
catalog.dataset_member    dataset_id, sample_id, val
```

**Annotations are scoped by label set, not by project.** A sample carries as
many annotations as there are label sets over it, so "presence, labelled
last year" and "boxes, labelled this year" coexist without either being
owned by the tool that produced it.

**`group_id` is a column, assigned at ingest by the subtype's rule** — one
per video for frames, unique per sample for standalone images. This retires
the mixed-corpora problem outright: one catalog holds both kinds, splitting
groups by a column, with no `[data] kind` and no directory globs. It also
retires the `[data] kind` setting shipped in `65e3a28`.

**Datasets are materialised, not queries.** A dataset is a saved selection
plus its split. That makes a training run reproducible by id, and it makes
validation membership stable *by construction*: a new version inherits
membership for samples it shares with the previous one and assigns only what
is new. That replaces the persisted-`val`-flag design this document
previously described, and retires `Sample.val` in the working tree.

`val` is per-dataset, which is what it always actually was — two projects
over one catalog should be free to hold out different samples.

## `modelling`

Model plugins, training runs, checkpoints and metrics, with each run
pointing at the dataset version it trained on. Lineage runs end to end:
checkpoint → dataset version → the exact samples and annotations behind it.

**Decoding moves to `catalog`.** `_load_rgb` inside the image classifier is
why satellite imagery would be painful today: a model hardcoding three
channels cannot take an eight-band GeoTIFF. If the catalog owns "read a
sample of this subtype into an array", the subtype axis stops leaking into
model code.

### The request is the contract

`modelling` is a library with an HTTP adapter, never HTTP-only. `labeller`
builds a request and hands it to either the in-process handler or an HTTP
client — and the in-process path **calls the same handler** rather than
bypassing it. Validation is one code path, error text is identical local and
remote, `pytest` needs no containers, and the boundary cannot rot because
both sides stay exercised.

A train request carries: model name, params, label set, dataset id.

### The backend is the only authority on what it can serve

No capability negotiation. A fetched capability list is stale by the time a
job is submitted, so the request-time check is needed regardless; building
both makes the list a cache that can only be wrong.

That pulls the schema check across too — `run_training` compares
`model.schema_type` against the project's schema in-process today; the
backend should validate "plugin installed, and it handles this task type" in
one place, on the side with the facts.

Two consequences: a bad param must come back as a **structured error naming
the parameter** rather than a 500 with a traceback, and an
`auto-labeller models` command should proxy the backend's list — not for
validation, but because nothing otherwise checks configuration until a
train, which can be after labelling a few hundred samples.

### Where a model comes from

Machine-level and job-level settings stay separated the way `config.py`
already states: *how this host reaches things* in `config.toml`, *what this
job is* in the job's own config.

```toml
# config.toml — this machine
[modelling]
url = "http://gpu-host:8000"    # omit to run in-process
```

The endpoint must not live with the job. If it did, one endpoint would mean
one model, a job could not move between a laptop and the GPU host without an
edit, and a backend could not serve several jobs — which was the reason to
have a backend.

**Entry points are now justified for model plugins.** They were rejected
earlier, correctly, because every plugin shipped in the same repo. A backend
makes a plugin an installable package someone else can publish.

**`ref = "model.py:Class"` survives for in-process mode.** Requiring a
package and an image rebuild for a quick experiment is a real regression,
and there is no container boundary in-process to force giving it up.

### Checkpoint version pinning

Checkpoints map output neurons to the class list *by position*, which is why
`add_classes` is append-only. Today the model code sits inside the project
and cannot change underneath it; with a remote backend, a plugin upgrade
between rounds silently invalidates the mapping.

So: record model name and version on the run, and refuse a checkpoint whose
recorded version does not match what the backend now serves.

## The deployment this is for

Three machines, not one host running containers:

```
minipc + external drive   Garage (S3-compatible) and the catalog index
desktop, Turing GPU       modelling
desktop or laptop         labelling
```

Two consequences that a single-host picture hides.

**"Shared storage" is object storage over a network, not a bind mount.** The
modelling host reads blobs across a link rather than off a disk, so reading
them one at a time in a training loop is the slow path and staging them
locally first is a real optimisation — which is what materialising becomes
in this topology, rather than a workaround for a missing mount. When Garage
or the index is unreachable, staging cannot help either, and that is an
error to report rather than something to work around.

**Sample ids are catalog-local, so a request that crosses machines
addresses samples by checksum.** The integer primary key is right inside one
catalog and meaningless outside it: if the labelling host and the modelling
host ever resolve against different instances, one id silently names two
different images. A checksum is globally meaningful by construction, which
is why the dataset manifest already carries one beside every id.

**Labelling from more than one machine reconciles at the catalog**, because
annotations are keyed ``(sample_id, label_set_id)`` and written as upserts.
Two machines labelling different samples merge cleanly. Two labelling the
same sample is last-write-wins with no conflict detection — adequate for one
person, and a real gap the day it is two.

## Deployment: two containers, not four

One of these boundaries is a data plane and does not want a network in it.

```
┌───────────────┐     HTTP      ┌──────────────┐
│   labeller    │──────────────▶│  modelling   │
│  + Label      │               │  (GPU host)  │
│    Studio     │               │              │
└───────┬───────┘               └──────┬───────┘
        │      both import catalog     │
        └──────────────┬───────────────┘
                       ▼
            Garage (shards) + Postgres (index)
```

**`labeller` ↔ `modelling` over HTTP.** Training is long-running, so it
wants to be a submitted job rather than a blocking call. The framework image
is multi-GB while the labelling image is small. And the payoff is locality:
`modelling` runs where the GPU is, labelling happens from anywhere, and a
model that got good enough serves other work without dragging an annotation
tool along. `ls_backend.py` is already a FastAPI service loading a model and
serving predictions — the modelling container is that generalised from
predict-only to predict-and-train.

**`catalog` is a library, not a service.** Training reads every sample's
bytes several times per epoch; HTTP in that path turns a range read into a
round trip inside the inner loop.

### The one exception: serving samples to a browser

Label Studio displays images by putting a URL in an `<img>` tag. A tar
member is a byte range, reached with a `Range` header — which a browser will
not send for an image load and a presigned URL cannot carry. **So the
labelling UI cannot fetch a sample out of a tar.**

The alternative to duplicating every image as a standalone object is a small
read API: `GET /sample/{id}` → range read → bytes, with Label Studio
pointed at it instead of at the bucket. One source of truth, and it fits the
split above — bytes for training go straight from object storage at full
speed, bytes for humans go through a Python hop at human speed, where it
costs nothing.

## Costs, recorded deliberately

**Portability.** `project.py` promises a project directory is "a
self-contained, portable labelling job." With data in a catalog and models
as plugins on a server, handing someone that directory gives them neither.
This is a real downgrade, accepted in exchange for an asset that outlives
any single job. Reproducibility moves to lineage — a run names a dataset
version and a model version — and the docstring should be corrected when the
change lands.

**The name.** `auto-labeller` will describe the smallest of the four
packages.

**Ordering.** Object storage and Postgres come before the HTTP split, not
after. Modelling on one machine reading a catalog on another *is* remote
storage, and there is nothing to be gained from putting modelling behind
HTTP while its catalog can only be a local directory.

**Infrastructure must not become mandatory.** If the catalog only speaks
Postgres and S3, nobody can run this repo without standing up a database and
an object store — which kills the runnable demo that is the highest-value
thing for a reader. The storage and index access want an interface with a
local implementation (filesystem plus SQLite) behind it. Sequenced late in
`roadmap.md`, but not dropped.
