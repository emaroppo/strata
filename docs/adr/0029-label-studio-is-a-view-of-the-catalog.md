# 29. Label Studio is a view of the catalog, and a queue is disposable

**Status:** accepted

## The decision

The catalog wins. A Label Studio project can be deleted and rebuilt and nothing
is lost: everything already answered arrives answered, and task ids are cached
rather than stored, rebuildable by listing, since a task's URL names its sample
by checksum (record 0013). The one thing kept in place is the live labeling
config, which is edited rather than regenerated.

## Why a view

Record 0013 keeps Label Studio's format out of the catalog. This is the other
direction: nothing the catalog needs lives only in Label Studio. A queue on a
desktop and a queue on a laptop reconcile through the annotations, never
through task ids; a project rebuilt after an accident is the same project.

## Why the live config is edited in place

Record 0016 argues against editing `project.toml` by regular expression. The
labeling config is the case where in-place editing is right: a reviewer tunes
columns, zoom and hotkeys by hand, and regenerating the XML from the schema
throws that away. A class is inserted at text level, a hotkey is offered only
when every existing class has one so a config that avoids them keeps avoiding
them, and a single-label config stays byte-for-byte unchanged so Label Studio
does not re-validate what did not move. This is recorded as the exception, not
as a habit.

## Consequences

- A task with no annotation is left alone rather than recorded empty, and a
  cancelled annotation is a skip.
- Deleting a project in Label Studio is a supported way to start over, and
  `push` recreates what the catalog knows.
