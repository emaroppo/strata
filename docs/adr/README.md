# Decision records

One file per decision that would otherwise have to be re-derived. Each says
what was decided, what it rules out, and — most importantly — what goes
wrong under the alternative, because that is the part nobody remembers six
months later.

These were recorded on 2026-09-12 from the reasoning the code had carried
in its docstrings since each decision was made; `roadmap.md` says when. A
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
