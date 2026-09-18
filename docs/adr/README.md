# Decision records

One file per decision that would otherwise have to be re-derived. Each says
what was decided, what it rules out, and — most importantly — what goes
wrong under the alternative, because that is the part nobody remembers six
months later.

Records 1 to 17 were written on 2026-09-12 from the reasoning the code had
carried in its docstrings since each decision was made; 18 to 39 on
2026-09-14, from a pass over every docstring and comment for decisions no
record yet stated. `roadmap.md` says when each was made. A
docstring now states what a function promises and, where a decision
shaped it, names the record here. `architecture.md` is the map; a record
is one road on it, with the reason it goes that way.

| | Decision |
|---|---|
| [0001](0001-a-sample-is-its-bytes.md) | A sample is its bytes: every reference that must survive a move is a checksum |
| [0002](0002-blobs-are-immutable-shards.md) | Blobs are immutable shards, and the local backend behaves like one |
| [0003](0003-a-dataset-version-is-frozen-and-inherited.md) | A dataset version is frozen, its sides inherited, its identity its answers |
| [0004](0004-the-manifest-is-the-contract.md) | The manifest is the contract between catalog and modelling, and `labels` holds it |
| [0005](0005-a-run-is-a-chain-in-a-database.md) | A run is a chain in a database, with an id that needs no coordination |
| [0006](0006-a-prediction-is-a-function-of-three-inputs.md) | A prediction is a function of three inputs, and nothing is ever invalidated |
| [0007](0007-one-handler-two-transports.md) | One handler, two transports: a round is submitted, not awaited |
| [0008](0008-ids-mean-nothing-outside-their-catalog.md) | Ids mean nothing outside their catalog, so a catalog has an identity |
| [0009](0009-disagreement-is-recorded-and-sources-are-ranked.md) | Disagreement is recorded, sources are ranked, and unlabelled is the absence of a row |
| [0010](0010-a-sample-type-is-a-plugin-and-canonical-is-not-normal.md) | A sample type is a plugin, and canonical form is not normalisation |
| [0011](0011-a-feature-is-a-role-not-a-fact.md) | A feature is a role, not a fact about the data |
| [0012](0012-the-review-queue-is-two-pools.md) | The review queue is two pools, and the unscored are left out |
| [0013](0013-label-studio-stops-at-the-adapter.md) | Label Studio stops at the adapter, and a URL is a credential |
| [0014](0014-a-label-set-declares-its-shape.md) | A label set declares its shape, and a model refuses before a round |
| [0015](0015-a-package-exports-its-contract.md) | A package exports its contract, and a module path across packages is a promise |
| [0016](0016-a-project-is-the-job-and-a-tool-extends-it.md) | A project is the job, and a tool extends it in a section of its own |
| [0017](0017-common-stays-whole-and-the-canonical-form-is-one-implementation.md) | `common` stays whole, and the canonical form is one implementation |
| [0018](0018-opening-never-creates.md) | Opening never creates, a new store is stamped at head, and a database is refused rather than upgraded in passing |
| [0019](0019-the-file-says-where-and-the-environment-holds-secrets.md) | The file says where, the environment holds secrets, and every process reads the same file |
| [0020](0020-a-host-holds-several-catalogs-and-a-project-names-its-own.md) | A host holds several catalogs, and a project names its own; nothing falls back to the default |
| [0021](0021-one-schema-two-dialects.md) | One schema, two dialects: the local catalog needs no infrastructure |
| [0022](0022-a-collection-is-where-a-sample-came-from.md) | A collection is where a sample came from, and every query names the ones it draws from |
| [0023](0023-a-grouping-is-a-metadata-key.md) | A grouping is a metadata key, and a version names the one it respects |
| [0024](0024-a-version-says-where-its-sides-began.md) | A version says where its sides began, and records the split it was given |
| [0025](0025-a-round-carries-its-split-as-a-realisation.md) | A round carries its split as a realisation, never its seed, and continues a parent only by a policy the caller states |
| [0026](0026-a-materialised-directory-is-whole-or-absent.md) | A materialised directory is whole or absent, and reused only when its manifest proves it |
| [0027](0027-an-annotation-keeps-its-history.md) | An annotation keeps its history, and a batch follows its answer |
| [0028](0028-an-import-is-trusted-until-a-person-looks.md) | An import is trusted until a person looks, and the look is a named batch's spot check |
| [0029](0029-label-studio-is-a-view-of-the-catalog.md) | Label Studio is a view of the catalog, and a queue is disposable |
| [0030](0030-a-command-renders-a-record-an-operation-returns.md) | A command renders a record an operation returns, refuses before it writes, and prints nothing from the library |
| [0031](0031-progress-is-reported-at-the-boundary.md) | Progress is reported at the boundary, silence is no news, and stopping is asked |
| [0032](0032-a-round-trip-is-per-batch.md) | A round trip is per batch, never per sample, and a re-run carries on from the last |
| [0033](0033-a-plugins-promise-is-an-executable-suite.md) | A plugin's promise is an executable suite it runs itself: models, preparers, sample types |
| [0034](0034-a-model-is-found-by-name.md) | A model is found by name, and its framework is an extra |
| [0035](0035-evaluation-is-one-implementation.md) | Evaluation is one implementation, and a model's own numbers are its own |
| [0036](0036-nothing-is-quietly-smaller.md) | Nothing is quietly smaller: what a step leaves out is counted and said |
| [0037](0037-a-stage-is-keyed-on-everything-upstream.md) | A stage is keyed on everything upstream, and a record is never invalidated |
| [0038](0038-a-manifest-need-not-come-from-a-catalog.md) | A manifest need not come from a catalog, and null means the producer did not say |
| [0039](0039-a-schema-answers-which-classes-a-value-asserts.md) | A schema answers which classes a value asserts, and the catalog indexes nothing else |
| [0040](0040-what-enters-a-catalog-is-declared-outside-it.md) | What enters a catalog is declared outside it, and a type's metadata is a contract |
