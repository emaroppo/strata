# 15. A package exports its contract, and a module path across packages is a promise

**Status:** accepted

## The decision

What a sibling package may use of another is what that package's
`__init__` exports. A cross-package import that names a module path
instead is a promise made knowingly: the module says so in its docstring,
and it is treated as public from then on.

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
- The remaining module-path imports between `labeller`, `modelling`,
  `project` and `catalog` are settled under the same rule: promoted to an
  export, or named in the module as a promise.
