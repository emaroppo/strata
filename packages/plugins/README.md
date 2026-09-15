# strata-plugins

First-party plugins for the strata packages, one directory per package
they extend and one distribution per plugin, so a host installs only the
converter or model it needs.

| plugin | extends | what it is |
|---|---|---|
| [`strata-prepare-video`](catalog/prepare-video/README.md) | `strata-catalog` | video into grouped frames |

A plugin registers through the entry-point group its package reads
(`strata.preparers`, `strata.sample_types`, `strata.models`); the package's
README says what the contract is, and the package ships the conformance
suite the plugin's tests run.

## Tests

Each plugin is tested from its own directory. Until the strata packages
are on an index, the ones a plugin builds on come from wheels built beside
this checkout:

```bash
.github/sibling-wheels.sh labels common catalog
cd catalog/prepare-video
uv sync --find-links ../../dist --group dev --extra test
uv run pytest
```

Inside the strata workspace, where this repository is `packages/plugins`,
`uv run pytest packages/plugins` from the workspace root covers every plugin.

`docs/adr/NNNN`, wherever a plugin's code says it, is a record in the strata
umbrella repository: https://github.com/emaroppo/strata/tree/main/docs/adr.
