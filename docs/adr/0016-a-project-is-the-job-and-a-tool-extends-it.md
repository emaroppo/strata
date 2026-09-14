# 16. A project is the job, and a tool extends it in a section of its own

**Status:** accepted

## The decision

`project.toml` is the job: the catalog and collections it draws from, the
label set it labels under with its task and classes, the sample type, and
the model. It is read through `strata.project`, a package below both
tools that use it. A tool keeps what is its own in a section the job
carries without reading, `[label_studio]` for the labeller, and in state
beside the file that is not part of a handoff. The labeller's view of a
project is a subclass that reads its section and builds the Label Studio
schema from the job: the task and classes are the job's, the media is the
sample type's, and a config of the project's own supplies control names
and layout and has to agree with the job on the rest.

The file is written through a TOML library that keeps comments, both when
it is scaffolded and when a class is appended.

## Why the job is its own package

The labeller ran the job and experiments varied it, and both read one
file; the file's definition lived in the labeller because that is the
tool the project began as. So `experiment` depended on the labeller for
the sole purpose of reading a project, and the project it read named a
Label Studio template in its label section.

Neither tool can own it. `experiment` is due to gain the stages that push
to and export from the labeller, at which point it depends on the
labeller; a job owned by `experiment` would then make the labeller depend
on the package that depends on it. `common` may name no domain object
and imports nothing from the workspace, and a project names every domain
object there is. What remains is a package of its own, and once it
exists the two tools are peers over it rather than one importing the
other.

## Why the file carries nothing tool-specific

A project file is copied between machines and outlives the tool that
collected its annotations (record 0013). With a Label Studio template
name in the label section and classes read from a Label Studio XML, the
job could not be stated without the tool. `[label_set] task` says what
is annotated; the media it is annotated over is what the sample type
already says; the tool derives its template from the two. A config of
the project's own used to be the source of the class list, and is now
rendering only, checked against the job: an XML offering a class the
job does not declare lets a reviewer apply a label the catalog then
refuses on export, which is the drift the check exists to catch.

## Why regex edits went

`add_classes` rewrote one line of the file by regular expression and the
scaffold built it by string concatenation. Both worked on the file they
had written and on nothing else: a class list split across lines, or a
section in another order, was rewritten wrongly with nothing raised. A
TOML library that round-trips comments edits the one value and leaves a
person's file as their own.

## Consequences

- `experiment` no longer depends on the labeller, and the labeller
  installs without an orchestrator.
- The job seeds the catalog's label set from `[label_set]` directly; the
  tool's schema is not on that path.
- A section the job does not own passes through unread. The labeller
  refuses one it does not know, so a misspelt section is still caught,
  by the tool that owns the rest of the file.
- The Label Studio project id lives only in the project's state, per
  instance; the file never carried one that meant anything on another
  machine.
- Anchoring a model reference at the project root is the project's
  (`model_ref`), through modelling's exported `absolute`; the labeller's
  round and an experiment's train stage ask the project rather than
  reaching into modelling's registry.
