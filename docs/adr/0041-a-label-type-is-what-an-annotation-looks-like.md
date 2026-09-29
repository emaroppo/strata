# 41. A label type is what an annotation looks like; a task is what it is for

**Status:** accepted

## The decision

What was called a label set's `task` — `classification`, `span`, `bbox` — is
its `label_type`: the shape an annotation takes. The schema's discriminator,
`[label_set]` in `project.toml`, a model's class attribute, a Label Studio
schema and the catalog's stats all say `label_type`, with the same values.
"Task" is kept for what the annotations are *for*: extracting entities,
anonymising a document. Several tasks may read one label type.

The old name is refused, not accepted beside the new one: a manifest says
format 2 and a format-1 manifest is rebuilt; a catalog's stored schemas are
rewritten by a migration; `[label_set] task` and a model declaring `task`
are each refused with the line to write instead.

## Why

A span label set was being asked two different questions. Entity extraction
asks whether each entity was found with the right label and bounds; the
emails project's anonymisation asks whether each one was hidden, and hidden
as one placeholder rather than several. The same spans, scored two ways, and
the second cannot be stated while the only name for "what this label set is
about" is the name of its shape. With the shape called what it is, a task can
name itself, declare the label type it reads, and sit beside another task
over the same spans as an equal.

## Why refused rather than accepted beside

Accepting both names means every reader of a schema, a project file or a
model carries the fallback for as long as any old file exists, and a file
written with both says two things. Every place the name was stored already
has a way to move forward: the manifest's format number (record 0004), the
catalog's migration chain (record 0018), and a project file or a model that
is read at one point where the refusal can name the fix. A model is the one
case where refusing matters most: without it, a plugin still declaring
`task` would inherit the default label type and be accepted as a classifier.

## Consequences

- The values are unchanged, so Label Studio template names (`text_span`) and
  prediction kinds are untouched.
- `strata-catalog-migrate upgrade head` is needed on an existing catalog, and
  materialised dataset versions are rebuilt on next use.
- `strata-catalog stats --json` reports `label_type`; `strata-labeller new`
  takes `--label-type`.
- The `evaluate` stage and `strata-evaluation` are organised by task, each
  task naming the label type it reads.
