# Architecture — planned direction

Status: **built.** The four packages exist, the labelling loop runs end to
end on the catalog, and the pre-catalog path has been deleted. Object
storage, Postgres, the sample-serving API and the HTTP split — listed here
as unbuilt while this was being written — are all in place; `roadmap.md`
records how that went.

Two things arrived after the restructuring and are marked where they appear:
a sample type's **canonical form**, and **preparers**, the surface that
converts a corpus into what a type stores.

This is still a design document rather than a description, so read a section
marked *not yet built* as a plan that may since have been decided
differently — the text-storage section is one such, and now says what
happened instead. Sequencing lives in `roadmap.md`; anything still owed
lives in `TODO.md`, which is the only list of it.

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
| `labels` | what an annotation *is*: value types, schema descriptors, the indexing contract; and the manifest a trainer is handed | — |
| `catalog` | samples, storage, grouping, annotations, datasets | `labels` |
| `modelling` | train and predict; model plugins; runs and checkpoints | `catalog`, `labels` |
| `labeller` | active learning, and the Label Studio adapter that feeds it | `catalog`, `modelling`, `labels` |

Acyclic, with `labels` as the leaf.

Two converter plugins sit outside the table. `strata-prepare-email` and
`strata-prepare-video` turn a corpus into a sample type the catalog admits;
each depends on `catalog`, and nothing depends on them.

`labeller` is deliberately thin — active learning plus a UI adapter. The
centre of gravity is the catalog.

### One repo, for now

A `uv` workspace, which the build already uses everywhere. That gives a
`pyproject.toml` per package, independently declared dependencies, separate
extras, and independent publishability — without a version-pinning dance on
every change touching two packages, which during a restructuring is most of
them.

The split is decided and not yet done. Each package moves to a repository of
its own, with its history; `deploy/minipc` goes with `catalog`, `deploy/gpu`
with `modelling`, and the labeller's one-off scripts with the labeller. This
repository stays, holding these documents.

What keeps the split possible in the meantime is a CI job that builds every
wheel and installs each package alone — the others coming from those wheels,
as they would from an index — before running its tests. In a checkout
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

**Label Studio's format must not go in it.** What `schemas/` is today is an
LS adapter wearing a schema layer's clothes: `Result` is an LS result dict,
`canonicalize` and `strip_volatile` exist to drop LS's volatile fields,
`label_config()` emits LS XML, `MEDIA_TAGS` parses it. If that becomes
`labels`, the catalog is shaped by a replaceable annotation UI.

So `labels` holds value types, schema descriptors, encode/decode/validate —
and LS's XML and result handling stay in `labeller` as a boundary adapter.

**It also holds the manifest**, and the digest the prediction cache keys
features on. Neither is an annotation, but both are files two packages must
read identically and neither may import the other: the catalog writes a
manifest and modelling trains from it; the laptop and the modelling host
both compute the digest. The manifest used to live in the catalog, and
modelling read it back by key name — so a renamed field arrived as nothing
rather than as an error.

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

**Not what was built, and worth saying so.** Documents go through blobs like
everything else — content-addressed, served by the same blob server, fetched
by Label Studio over the same signed URL. The index holds no content. What
made the plan above unnecessary was that the blob path turned out to cost
text nothing, and one storage path is a great deal simpler than two; what it
gives up is the free full-text search, and the headers-as-columns idea that
went with it. Headers are sample metadata instead. If either is wanted
later, this section is the argument for it.

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
than the tests do. A database with tables and no revision predates
migrations and is **refused on open**: it is at the baseline, and stamping
it head would have it claim columns it does not have. A test diffs the
chain against `tables.py`, because a chain nothing exercises rots.

Each package ships its chain and the command that runs it,
`strata-catalog-migrate` and `strata-modelling-migrate`, so there is no
`alembic.ini` and an installed wheel migrates its own store.

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

## Sample types: a plugin surface in `catalog`

*Decided after two days of running the loop. Built, and since extended by a
fourth responsibility and a companion surface — both at the end of this
section.*

What a sample **is** — a photograph, a video frame, a satellite scene, a
document — belongs to the catalog. Today it is scattered, and mostly in the
wrong package: an extension list in `labeller.schemas.media`, a grouping
rule in `to_catalog.group_id_for`, and a hardcoded `metadata_for` lambda in
`ingest`. So the labelling tool defines what a sample is, and the catalog
that stores it does not.

A sample type is a plugin owning the three things that differ per kind of
data at ingest:

```python
class Satellite(Image):
    media = "image"
    subtype = "satellite"
    extensions = frozenset({"tif", "tiff"})

    def metadata_for(self, path) -> dict: ...   # bounds, CRS, capture time
    def group_id_for(self, path) -> str | None: ...  # by scene, or None
```

**Inheritance is safe here**, unlike for label sets. Classes map to a
checkpoint's output neurons by position, so a parent label set gaining a
class would silently reindex its children — which is why label sets are
copied rather than inherited. A sample type is code, not stored data, and
`Satellite(Image)` overriding one method has nothing at a distance.

**Nothing in the schema changes.** `sample.media` and `sample.subtype` are
free strings, `metadata` is arbitrary JSON, `group_id` is per sample. That a
new type needs no migration is the sign the concept was factored right
before it was finished.

Three decisions, settled:

**Extensions are an allow list, not a discovery filter.** Ingest walks what
it is pointed at; the user is responsible for a sensibly arranged folder.
Extensions are then a check — files outside the list are skipped *and
reported*, with the count and the extensions named, and a walk that matches
nothing is an error rather than an empty success. Filtering silently is how
a corpus ends up quietly smaller than the directory it came from, which is
the failure this whole design keeps running into.

**`labeller` keeps only Label Studio.** `Media` dissolves: `data_key` and
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

`[data] kind` retires into `[data] type`, which also separates *what a
sample is* from *how it groups* — currently the same word, and the reason
frames ingested as plain images silently ruin a train/val split.

### A fourth responsibility: canonical form

*Added later, on contact with text.*

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

*Added later, for the same reason.* A type says what the catalog holds;
almost no corpus arrives that way. Mail arrives as `.eml` or as message
JSON, frames arrive as video — and the scripts that once made frames were
deleted with the pre-catalog tooling, so nothing in the tree made them.

A **preparer** converts a corpus into what a type stores, writes the files
and an index of what it knew, and stops. `ingest` still catalogues. Keeping
the two apart is what stops a converter becoming a second implementation of
content addressing, grouping and collections.

Two consequences worth stating.

**Grouping becomes declared rather than inferred.** `Frames.group_id_for`
read the directory a frame sat in, which is a convention two pieces of code
have to agree about. What extracted the frames *knows* they are one video,
and now says so in the index; the directory rule stays as the fallback for a
corpus nobody prepared.

**Determinism is the contract that matters.** A conversion that produces
different bytes on a second run re-checksums the corpus, and re-checksumming
an annotated corpus does not lose the annotations — it detaches them, which
is the quieter and worse failure. `PreparerContract` checks that, along with
the output being admitted and already canonical for the type it claims to
produce.

They ship as their own distributions: a converter carries a mail parser or a
video decoder, and a catalog should not.

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
