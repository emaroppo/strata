# Architecture

The map as built: what the packages are, what each owns, and the contracts
between them. `orchestrator.md` holds the experiment file's design in full;
`roadmap.md` is what is decided and not yet here, and `TODO.md` its tasks.
Where a section says why something is the way it is, that is the reasoning
that survived contact with real data; where the reasoning was a decision
with a live alternative, it is an ADR in `adr/`.

---

## What the system is for

The durable assets are **a labelled data catalog** and **a model catalog**.
The labelling tool is scaffolding that produces the first one. Anything that
makes the catalog depend on the scaffolding has the relationship backwards.

That principle decides most of what follows.

## The packages

Seven live under a `strata` PEP 420 namespace — `strata.labels`,
`strata.catalog`, `strata.modelling`, `strata.project`, `strata.labeller`,
`strata.common`, `strata.experiment` — distributed as `strata-labels` and so on. Namespacing
rather than bare top-level names because `catalog` and `labels` collide
with almost anything in a shared environment, and because another package
then costs nothing. Independent
installability is unaffected: this is how `google.cloud.*` works.

Short names are used below for readability.

| Package | Owns | Depends on |
| --- | --- | --- |
| `labels` | what an annotation *is*: value types, schema descriptors, the indexing contract; and the manifest a trainer is handed | — |
| `catalog` | samples, storage, grouping, annotations, datasets | `labels` |
| `modelling` | train and predict; model plugins; runs and checkpoints | `catalog`, `labels` |
| `project` | the job as a file: catalog, collections, label set, model; the host's settings | `catalog`, `modelling`, `labels` |
| `labeller` | active learning, and the Label Studio adapter that feeds it | `project`, `catalog`, `modelling`, `labels` |
| `common` | what `catalog` and `modelling` both need and neither owns: migration plumbing, an engine factory, a service bootstrap, an entry-point resolver, the canonical form that gets hashed | — |
| `experiment` | an experiment as a file: stages from a config, a grid over them, a ledger of what ran | `project`, `catalog`, `modelling`, `labels`, `common` |

Acyclic, with `labels` and `common` as the leaves and the two tools at the
top: `labeller` and `experiment` are peers over `project`, the job both
read, and neither imports the other (`docs/adr/0016`). `common`
declares no dependency of its own; what a module needs sits behind an
extra, so a plugin resolver never pulls in a database driver.

Two converter plugins sit outside the table. `strata-prepare-email` and
`strata-prepare-video` turn a corpus into a sample type the catalog admits;
each depends on `catalog`, and nothing depends on them.

`strata-common` sits under `catalog` and `modelling`, holding what both
need and neither owns — running a migration chain from an installed wheel,
starting a service from the environment, resolving a name through an
entry-point group, the canonical form that gets hashed — and nothing else:
it declares no dependency
of its own, its extras name what each module needs, and it never mentions
a label, a sample or a run. It is not `labels`, which every consumer already
imports and which stays about what an annotation is.

`labeller` is deliberately thin — active learning plus a UI adapter. The
centre of gravity is the catalog. `project` is thinner still: the one
file the tools share, and what a tool keeps of its own goes in a section
the job carries without reading.

### One repo

A `uv` workspace, which the build already uses everywhere. That gives a
`pyproject.toml` per package, independently declared dependencies, separate
extras, and independent publishability — without a version-pinning dance on
every change touching two packages. The split into a repository per package
is on the roadmap; the workspace is what keeps it possible.

What keeps it possible is a CI job that builds every wheel and installs
each package alone — the others coming from those wheels, as they would
from an index — before running its tests. In a checkout
everything is installed together, so a package quietly relying on one it
does not declare passes every other job; this is the one it fails.

### Releasing the packages separately

The workspace keeps the packages in step; published separately, they are
not. Wherever one package writes what another reads, an old release of one
will meet a new release of the other, so each such contract says how it may
change:

- **Versions are per package.** Each is released on its own, at 0.x, where a
  minor release may break things. A package depending on another requires
  the minor it was tested with — `strata-labels>=0.1,<0.2` — so moving to a
  new one is a deliberate change in the dependent, not something an install
  does on its own.
- **The manifest** (`strata.labels`) states its format, and a reader refuses
  one it does not know. The number goes up only when an older reader would
  misread a newer file; a field added with a default does not need it.
- **The wire** between the laptop and the modelling host states a protocol,
  checked on `/healthz` before anything is sent, on the same rule.
- **A label type** is a member of the unions in `strata.labels`, and an
  older reader fails loudly on one it does not know. Adding one is a minor
  release of `labels`, with a sample in `strata.labels.examples`. A consumer
  supports it once it has released requiring that version and its own
  label-type tests pass for it. Renaming or removing a field of an existing
  type is a breaking release.
- **Label-type tests live with each layer.** `labels` checks what it alone
  can; the catalog, modelling and the labeller each run their own layer
  against every sample `labels` ships. None reaches across a package
  boundary, so each runs in its own repository, and a new type fails in
  each consumer until that consumer handles it.
- **The model contract** lets a caller ask a model to stop early: `on_epoch`
  may return `True`. Honouring it is optional, so a caller can start asking
  without breaking any model that does not listen.
- **Migrations ship in the package.** `strata-catalog-migrate` and
  `strata-modelling-migrate` run the chain inside the installed wheel, so
  upgrading a package and then its database needs nothing from a checkout.

## `labels`

The neutral representation, shared by everything.

**Label Studio's format stays out of it.** `labels` holds value types,
schema descriptors, encode/decode/validate; Label Studio's XML and result
handling live in `labeller`, under `strata.labeller.labelstudio`, as a
boundary adapter. Were they in `labels`, the catalog would be shaped by a
replaceable annotation UI. Storing canonicalised Label Studio results was
right while Label Studio was the centre — predictions and annotations
shared one format and its own tools worked on a handoff — and wrong as the
storage format of a durable catalog: a vendor wire format in a permanent
record, scrubbed of its volatile fields on the way in.

**The indexing contract.** The catalog cannot index opaque JSON, but it does
not need to understand every task type either. It needs each schema to
answer one question: *which classes does this annotation assert?* That is
`classes_asserted` on the schema in `strata.labels`. A new task type
implements the contract and becomes queryable without the catalog changing.

**A schema also declares what shape its values may take.** Spans were the
case that forced it: Label Studio's model is a region with a *list* of
labels, and it will let a reviewer draw two regions across one phrase. A
label set now says whether either is meaningful for the job —
`multi_label` for a region carrying several labels, `overlapping` for two
regions intersecting, both false by default and deliberately separate
questions.

The declaration is what lets a model refuse. BIO tagging gives each token
one tag, so it can represent neither; without somewhere to say so, the
tagger trains on a projection of the label set and is scored as though it
had learned the whole thing. An annotation tool being able to express more
than the layer storing it is the wrong way round, and this is where the two
are reconciled.

**The rule that keeps it from becoming a monolith with extra steps:** no
I/O, no storage, no SDK, no framework. Pure types and pure functions. Shared
kernels are where coupling hides, so this belongs in the package docstring.

## `catalog`

### Storage: shards in object storage, index in Postgres

Two blob backends behind one interface, and two index backends behind
another, as separate axes. A catalog on one machine is a directory: a
SQLite index and one file per blob. The shared one is a Postgres index and
tars in S3-compatible object storage (Garage, self-hosted) — packed rather
than stored as individual objects, because small-object overhead and
listing cost make per-file storage the wrong shape at volume.
`catalog-repack` moves the blobs from the first to the second, and nothing
else changes.

Tar has no index, so the index records `(location, offset, length)` per
sample. Tar members are contiguous, so one sample is one HTTP range
request. That gives two access modes:

- **Sparse** (labelling, review) → one range request per sample.
- **Dense** (materialising a version) → whole shards, streamed in shard
  order, into a local read-through cache — so materialising a version is a
  second of hard links after the first fetch rather than minutes of
  transfer.

Two rules:

- **Shards are immutable.** You cannot append to a tar in object storage
  without rewriting it. New data means new shards; removal is a tombstone
  in the index, `deleted_at`, and a compaction pass later.
- **Pack with locality.** Keep a video's frames in one shard, so a shard
  tends to fall on one side of a split and dense reads stay dense.
  100MB–1GB per shard.

### Text goes through blobs too

Documents are content-addressed blobs like images, served by the same blob
server and fetched by Label Studio over the same signed URL; the index
holds no content, and mail headers are sample metadata. Content in the
index instead — no serving hop, full-text search for free, headers as
columns — was the plan, and the blob path turned out to cost text nothing,
so one storage path won. The other is kept as a proposal, for the day
full-text search is wanted.

### Schema

```
catalog.catalog_identity    id, created_at

catalog.sample              id, location, offset, length, checksum, media,
                            subtype, metadata JSON, ingested_at, deleted_at
catalog.sample_collection   sample_id, collection

catalog.label_set           id, name, schema JSON (task type, classes, ...)

catalog.annotation          sample_id, label_set_id, state, value JSON,
                            source, updated_at
                            PK (sample_id, label_set_id)
catalog.annotation_class    sample_id, label_set_id, class_name
                            -- derived on write via labels' indexing contract
catalog.annotation_conflict sample_id, label_set_id, kept_value,
                            other_value, other_origin, noticed_at

catalog.dataset             id, name, version, label_set_id, query,
                            annotation_digest, val_ratio, holdout_ratio
                            (each asked and achieved), group_by, created_at
catalog.dataset_member      dataset_id, sample_id, side
```

**Annotations are scoped by label set, not by project.** A sample carries as
many annotations as there are label sets over it, so "presence, labelled
last year" and "boxes, labelled this year" coexist without either being
owned by the tool that produced it.

**A grouping is a metadata key, and nothing groups unless a project asks.**
Frames carry `video`, written at ingest by the sample type; a preparer or a
project can write any key of its own — the actor in frame, the thread a
message belongs to. A version is frozen with `group_by` naming the key
whose values stay on one side, or none, and records which. So the same
samples can be split by video for one study and by actor for another, a
grouping is just another dimension to query on, and the catalog enforces
none of them on its own.

**Datasets are materialised, not queries.** A dataset is a saved selection
plus its split. That makes a training run reproducible by id, and it makes
validation membership stable *by construction*: a new version inherits
membership for samples it shares with the previous one and assigns only what
is new.

The side is per dataset — `train`, `val` or `holdout`, and a holdout never
reaches a model — which is what it always actually was: two projects over
one catalog are free to hold out different samples.

**A warm start follows the dataset name across versions, and inheritance
is what makes that safe.** Every round freezes a new version, and the
model carried from v3 to v4 has never seen v4's validation or holdout
because v4 kept every side v3 decided. A version may instead re-split
from nothing — another grouping, another seed, a benchmark's own split —
and then records the version its sides began at. A warm start never
reaches back past that: the round after a re-split starts cold, once, and
the lineage continues from there.

**A version is its samples *and its answers*.** Identity was the selection
alone, which meant correcting a label returned the previous version and a
round trained on the materialised copy of the values it had just corrected.
It carries a digest over its members' annotations — state, source and value
— and a digest rather than a timestamp because `updated_at` is
second-resolution: one bulk annotate writes thousands of rows sharing a
second, so a correction inside that second moves no watermark.

### Schema changes are migrations

`create_all` builds a schema and cannot evolve one: it adds tables and
never columns, so the first change to an existing table broke every
database in the wild. Alembic, with a history per store — a catalog is a
host's and may be Postgres, a run store is one project's and is always
SQLite, and they change at different times for different reasons.

A database `create_all` just built is stamped at head, because it is at
head by construction and replaying the chain in every test would cost more
than the tests do. That happens only in `Catalog.create`, which the
commands that put data in ask for. **Opening never creates**: `connect`
checks the recorded revision against head and touches nothing else, so a
command that consults a catalog cannot leave an empty one behind or issue
DDL against a live one. An index with no catalog in it is refused as
missing; a database with tables and no revision predates migrations and
is refused too, since it is at the baseline and stamping it head would
have it claim columns it does not have. A test diffs the chain against
`tables.py`, because a chain nothing exercises rots.

Each package ships its chain and the command that runs it,
`strata-catalog-migrate` and `strata-modelling-migrate`, so there is no
`alembic.ini` and an installed wheel migrates its own store.

## `modelling`

Model plugins, training runs, checkpoints and metrics, with each run
pointing at the dataset version it trained on. Lineage runs end to end:
checkpoint → dataset version → the exact samples and annotations behind it.

**Decoding stays in the model, for now.** The image baseline reads a path
into three channels itself, so a subtype whose bytes are not RGB — an
eight-band GeoTIFF — needs a model that knows how to read it. Moving "read
a sample of this subtype into an array" into the catalog, per sample type,
so the subtype axis stops leaking into model code, is a proposal.

### The request is the contract

`modelling` is a library with an HTTP adapter, never HTTP-only. `labeller`
builds a request and hands it to either the in-process handler or an HTTP
client — and the in-process path **calls the same handler** rather than
bypassing it. Validation is one code path, error text is identical local and
remote, `pytest` needs no containers, and the boundary cannot rot because
both sides stay exercised.

A train request carries the dataset directory, the model name and its
params, and the parent run to warm-start from. A round submitted to the
host carries the catalog id and the dataset's name, version and annotation
digest instead of a directory: the host materialises it with a cache of
its own rather than having it shipped, and refuses a mismatch on either.
It also carries the split as the caller's directory realised it, one
letter per sample with a digest of the order, which the host applies to a
copy of what it materialised when it differs from the version's own — so
a split drawn on a laptop is what the host trains on, or the round is
refused, never silently the catalog's assignment instead.

### The backend is the only authority on what it can serve

No capability negotiation. A fetched capability list is stale by the time a
job is submitted, so the request-time check is needed regardless; building
both makes the list a cache that can only be wrong.

So the check that a plugin is installed and handles this label set's task
happens in the handler, on the side with the facts — the same handler
in-process and behind HTTP — and a refusal comes back as a structured error
the client renders, never a 500 with a traceback. The list is not used to
validate a round, but `strata-labeller models` asks for it — and says
whether a project's model is on it — so a project pointed at a model the
host does not have finds out before a few hundred samples are labelled
against it rather than at its first train.

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

**Model plugins are entry points**, in the `strata.models` group. They
were rejected while every plugin shipped in one repo, and a backend is what
justified them: it makes a plugin an installable package someone else can
publish.

**`ref = "model.py:Class"` works in-process only.** Requiring a package and
an image rebuild for a quick experiment is a real regression, and there is
no container boundary in-process to force giving it up. A backend refuses a
file reference and says what to do about it — register the model as an
entry point, or run the round locally — because a `model.py` resolvable
only on the machine that wrote it cannot run anywhere else either.

### Checkpoint version pinning

Checkpoints map output neurons to the class list *by position*, which is why
`add_classes` is append-only. With a remote backend, a plugin upgrade
between rounds would silently invalidate the mapping. So a run records the
model's name and version, and a warm start from a checkpoint whose recorded
version is not the installed one is refused.

### A model can be told what is already known

A target is what a model is asked for; a feature is something already known
that it may be told. Until there was a channel, a model received a path and
a target and everything else about the sample stopped at the catalog.

**Role is per job, not per annotation.** One annotation is the target of the
project that owns it and a feature of another, at the same time, over one
catalog — only the declaration differs. So a feature names *where to read a
value*: another label set, or a metadata key for values with no label shape.
That is also what makes a catalog's annotations compound rather than
accumulate: what one round acquires is what a later project is told.

Two consequences worth stating, because both were nearly got wrong:

**A feature must cover the project's collections**, and that is a
precondition to count rather than infer. `push` scores the whole unreviewed
pool, so a sample without a value cannot be scored — and a queue that only
surfaces covered samples never gets the rest labelled, which is a bias
nobody chose.

**A prediction became a function of three things.** The cache was keyed on a
checkpoint and some bytes, on the stated grounds that both are immutable. A
feature is neither. The digest went into the *key* rather than becoming a
policy to invalidate on, which keeps the original property literally true:
nothing is ever invalidated, and a corrected feature simply misses.

## `experiment`

The top of the graph. A project is the durable job — catalog, label set,
collections, model. An experiment is a separate file that references one
and adds variation: an ordered list of stages, each a registered name with
literal arguments, and a grid of values to vary. Several experiments per
project is the normal case, which is why it is not a section of
`project.toml`.

**A stage is a function taking a request and a context and returning a
record.** The catalog's stages freeze a version, materialise it, and read
or draw the split; modelling's train — here from a directory, or on the
host from a dataset's identity, the same record either way — and score one
side by one implementation. Records name what they made by identity and
never embed it. The command line calls the same functions one at a time;
the orchestrator calls them from the file. Neither has a second
implementation, and nothing shells out to a command.

**The file hashes, and the hash is the identity.** TOML is what a person
edits; canonical JSON — `strata.common.canonical`, the rules
`strata-post-process` and `strata-feature-store` import too — is what is hashed,
with the project in it by its declared name rather than by the path used
to find it. A trial is the file with its overrides written in. A stage's
key is the hash of the spec through that stage, the version of the
implementation that ran it, the request as built from the project and
what upstream produced, and the catalog in use — so an edit to
`project.toml` or a rerun upstream moves the key rather than reusing a
record made under other inputs.

**The ledger is what makes a rerun cheap.** Under the project, every
record by its key, and a directory per trial holding a copy of each record
it used. A stage whose key already has a record is handed downstream as if
it had run, so trials that agree through a stage share it, and a change
reruns only what is downstream of it. Nothing is invalidated: a changed
argument changes every key after it. Two of the stages cannot be
deterministic — training, and a person reviewing — so the hash is the
request's identity and the record binds it to an output; skipping is a
decision about cost, and the record says which run it produced rather than
promising the same one again.

**A grid needs every trial cold, or pinned to one parent**, never
warm-started from the previous trial, and it is refused at load otherwise.
Selection reads validation; the result is reported on a holdout the study
never sees, which the catalog assigns as a third side of the inherited
split. By default a trial reuses the sides the version carries; a seed on
the `split` stage draws its own, and the draw is recorded either way.

**What a run saw is on the run.** The run store records, beside each run,
which side every sample of its manifest was on and which experiment file
asked for it. So a study is a query over the store, and a surprising
number can be asked which samples the model was shown — whether the split
was inherited from the version or drawn from a seed, the two read the
same.

**Registry, not entry points.** A hand-maintained table of five stages,
readable in one place. There is no third-party stage, and a plugin seam
is designed at the third implementation; the three entry-point groups the
catalog and modelling already have stay as they are.

The first study, a learning-rate grid over a real project, is in the
README's results. What it taught is recorded in `orchestrator.md`: a
grid over one parameter merges over the project's parameters rather than
replacing them, and an exact-set score is not an accuracy for a label set
that carries two classes per sample.

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
same sample on one catalog is last-write-wins. Across two catalogs — a
laptop working offline on a copy — `catalog-merge` copies what the target
lacks, is silent where both agree, and records a conflict where they
disagree, which the review queue puts back in front of a person rather than
resolving.

## Two services, not four

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
tool along. The modelling service, `strata-modelling`, is a FastAPI app
over the same handlers: submit a round, poll it, reattach to it after the
client went away. It runs under a systemd user unit on the GPU host,
configured entirely through the environment; a container is on the
roadmap, and will be a second thin wrapper over the same contract.

**`catalog` is a library, not a service.** Training reads every sample's
bytes several times per epoch; HTTP in that path turns a range read into a
round trip inside the inner loop.

### The one exception: serving samples to a browser

Label Studio displays images by putting a URL in an `<img>` tag. A tar
member is a byte range, reached with a `Range` header — which a browser will
not send for an image load and a presigned URL cannot carry. **So the
labelling UI cannot fetch a sample out of a tar.**

The alternative to duplicating every image as a standalone object is a
small read API, `strata-blobs`: `GET /blob/{checksum}` → range read →
bytes, with Label Studio pointed at it instead of at the bucket. The URL is
signed with an HMAC over the checksum, so a leaked link opens one image;
and it is keyed by content rather than sample id, because that is the key
Label Studio already holds, it survives a repack, and what cannot change is
cacheable forever. One source of truth, and it fits the split above — bytes
for training go straight from object storage at full speed, bytes for
humans go through a Python hop at human speed, where it costs nothing.

## Sample types: a plugin surface in `catalog`

What a sample **is** — a photograph, a video frame, a satellite scene, a
document — belongs to the catalog, not to the labelling tool, which once
defined it in three places: an extension list, a grouping rule and a
metadata lambda.

A sample type is a plugin owning what differs per kind of data at ingest:

```python
class Satellite(Image):
    media = "image"
    subtype = "satellite"
    extensions = frozenset({"tif", "tiff"})

    def metadata_for(self, path) -> dict: ...   # bounds, CRS, capture time, scene
```

Anything a split might group by — the scene, the video — is a key in that
metadata, and a project names it when it freezes a version.

**Inheritance is safe here**, unlike for label sets. Classes map to a
checkpoint's output neurons by position, so a parent label set gaining a
class would silently reindex its children — which is why label sets are
copied rather than inherited. A sample type is code, not stored data, and
`Satellite(Image)` overriding one method has nothing at a distance.

**Nothing in the schema changes.** `sample.media` and `sample.subtype` are
free strings and `metadata` is arbitrary JSON. That a new type needs no
migration is the sign the concept was factored right before it was
finished.

Three decisions, settled:

**Extensions are an allow list, not a discovery filter.** Ingest walks what
it is pointed at; the user is responsible for a sensibly arranged folder.
Extensions are then a check — files outside the list are skipped *and
reported*, with the count and the extensions named, and a walk that matches
nothing is an error rather than an empty success. Filtering silently is how
a corpus ends up quietly smaller than the directory it came from, which is
the failure this whole design keeps running into.

**`labeller` keeps only Label Studio.** `data_key` and
the template name are Label Studio's wire format and config selection, and
both derive from the type's `media` string. What a file *is* stops being the
labelling tool's business.

**Built-in types are entry points too**, declared in `catalog`'s own
distribution exactly as the baselines are in `modelling`'s. One lookup path,
and `available()` answers truthfully for everything — which matters more
here than for models, because a type that fails to resolve is a data
problem: samples ingested with the wrong subtype, or not at all. The cost is
that distribution metadata has to survive deployment; `available()` coming
back empty is at least loud.

**Built-in names are reserved.** A plugin registering `image` would change
how everything ingests and nothing would say so, so it is refused at load.
One lookup path does not mean one namespace to fight over.

### Substitutability, in code and in queries

Where an image is expected, a satellite scene should do. That has to hold in
two places that work differently.

**In code** `issubclass(Satellite, Image)` answers it, and it composes: a
later `Multispectral(Satellite)` substitutes for both.

**In queries** it cannot — the database holds strings. So `subtype` is a
**path**, and selecting one matches its descendants, exactly as collections
already work: `satellite` matches `satellite/multispectral` and never
`satellite_old`. The class chain generates the path, so the prefix matching
`_within` already does is reused rather than reinvented.

```
plain                       Image
frames                      Frames(Image)
satellite                   Satellite(Image)
satellite/multispectral     Multispectral(Satellite)
```

Two invariants, checked at registration because both fail silently:

- **A subclass may not change `media`.** `Satellite(Image)` declaring
  `media = "raster"` would break substitution with nothing to show for it —
  a query for images would quietly stop returning satellite scenes.
- **The stored path must be the class chain.** Otherwise the string and the
  hierarchy drift, and the two answers to "is this an image" disagree.

The stored pair is a denormalisation of the hierarchy, not an independent
fact.

A project declares `[data] type`, which says what a sample is, and
`[catalog] group_by`, which says what stays together when a version is
split — two separate statements, where one word for both was why frames
ingested as plain images silently ruined a train/val split. A project
written with the old `[data] kind` is refused with the command that
rewrites it, rather than guessed at.

### A fourth responsibility: canonical form

A type also says what form its bytes are stored in. For images that is
nothing — the default returns them untouched, and ingest reads no file at
all for such a type, so a corpus is still hardlinked rather than copied. For
text it is UTF-8, LF, NFC and no BOM.

It sits here rather than anywhere else because it is a fact about the data,
and it earns its place for a reason images never surfaced: a span annotation
is a pair of character offsets, so the document a reviewer's browser
rendered and the document a tokenizer reads have to be the same characters.
A browser normalises line endings on its own. Measured on one prepared
corpus, 3.2% of documents carried CRLF, and a 144-document slice put 19
spans on the wrong characters when their offsets were carried across
unmapped.

**Canonicalisation, and deliberately not normalisation.** The test is
whether two independent implementations would produce identical bytes.
Consistent column names or key ordering would not pass it, and a checksum
that depends on our own release breaks the property `merge` is built on:
content identifies a sample, so two hosts on slightly different releases
must still agree about what a sample is. Encoding is refused rather than
guessed for the same reason a merge refuses rather than resolves — a
mojibake document ingests, renders as something plausible, and is annotated
against characters that were never there.

### The companion surface: preparers

A type says what the catalog holds;
almost no corpus arrives that way. Mail arrives as `.eml` or as message
JSON, frames arrive as video — and nothing in the catalog makes frames.

A **preparer** converts a corpus into what a type stores, writes the files
and an index of what it knew, and stops. `ingest` still catalogues. Keeping
the two apart is what stops a converter becoming a second implementation of
content addressing, grouping and collections.

Two consequences worth stating.

**Grouping becomes declared rather than inferred.** The frames type used to
read the directory a frame sat in, which is a convention two pieces of code
have to agree about. What extracted the frames *knows* they are one video,
and says so in the index under `video`; the directory rule stays as the
fallback for a corpus nobody prepared.

**Determinism is the contract that matters.** A conversion that produces
different bytes on a second run re-checksums the corpus, and re-checksumming
an annotated corpus does not lose the annotations — it detaches them, which
is the quieter and worse failure. `PreparerContract` checks that, along with
the output being admitted and already canonical for the type it claims to
produce.

They ship as their own distributions: a converter carries a mail parser or a
video decoder, and a catalog should not.

## Costs, recorded deliberately

**Portability.** A project directory was once a self-contained, portable
labelling job. With data in a catalog and models as plugins on a server,
handing someone that directory gives them neither. A real downgrade,
accepted in exchange for an asset that outlives any single job;
reproducibility is lineage instead — a run names a dataset version and a
model version.

**The name.** The repository, the namespace and every command are
`strata`. The labelling tool the project began as, `auto-labeller`, is
one package among seven, and its command is `strata-labeller` like the
rest.

**Infrastructure is not mandatory.** A catalog is a directory — a SQLite
index, one file per blob — until it is pointed at Postgres and a bucket,
and the two are separate axes. Without that, nobody could run this without
standing up a database and an object store, which would kill the runnable
demo that is the highest-value thing for a reader.
