# 15. A package exports its contract, and a module path across packages is a promise

**Status:** accepted

## The decision

What a sibling package may use of another is what that package's
`__init__` exports. A cross-package import that names a module path
instead is a promise made knowingly: the package lists the module in
`PUBLIC_MODULES` in its `__init__`, and it is treated as public from
then on. The dependency graph test reads that list from the installed
package and refuses any other path, so the promise is checked wherever a
consumer runs its tests, before and after the packages are repositories
apart.

## Why

The packages are to be released separately. From that release on, every
`from strata.x.y import` in another package is an API frozen by an
accident of file layout, and moving a module becomes a coordinated
release across repositories. Whether a path is public has to be decided
before then, once, rather than discovered by whoever first breaks it.

`strata.labeller` exported nothing and had a consumer: `experiment`
imported its project and settings modules directly. The package had a
public surface without ever having declared one, which is the failure
this rule exists to close.

## Consequences

- `labeller` exported `Project`, `ProjectError` and `Settings`, which was
  what `experiment` needed. The job then moved below both (record 0016),
  so the labeller exports its own view of a project and nothing in the
  workspace imports it today. The labelling loop, the review queue and
  the Label Studio adapter stay the package's own.
- `experiment` and `labeller` import the job from `strata.project`, not
  from its modules.
- `modelling` exports `absolute` beside `resolve`: the two read the same
  reference syntax, and the project anchors references through it.
- Every module path in use between the packages stays as it is and is
  promised: `catalog.config`, `catalog.stages`, the type and preparer
  registries and the feature specs; `modelling.stages`, its remote
  client and wire, and the plugin registry; every module of `common`.
  A promise is preferred over a promotion where the module is a layer
  with a shape of its own, and a flat `__init__` would hide it.
- Signing was the one reach-in to move rather than promise: the catalog
  hands out the URL its server verifies, and a promise that consumers
  hold the secret was not one to keep.
- A promised module that moves is moved in every consumer in the same
  change, never left behind as a re-exporting module. Promoting one to
  an export later is the reverse edit, and the test names every
  consumer that still uses the path.
- The catalog is the durable asset: every other package is a producer or
  a consumer of what it holds, and annotations outlive the tool that
  collected them. So it may import `labels`, the standard library and its
  own optional storage drivers, and never the labeller, modelling, Label
  Studio or an ML framework.
