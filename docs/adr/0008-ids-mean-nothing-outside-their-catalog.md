# 8. Ids mean nothing outside their catalog, so a catalog has an identity

**Status:** accepted

## The decision

A catalog carries an identity, minted once when it is created and kept by
any copy of it. Everything that holds a sample id outside the index — a
run, a materialised manifest, the Label Studio task map, a round sent to a
host — records which catalog issued it, and refuses to be read against
another. A copy preserves primary keys.

## Why

A sample id, a dataset name and a collection all mean something *within*
one catalog. A map written against one catalog and read against another
is not wrong in any way a computer can see: every id exists on both sides
and names a different sample. Pushing from it attaches a prediction to the
wrong image; exporting through it files a reviewer's answer against the
wrong sample; `unskip` deletes answers on unrelated tasks. Nothing raises,
at any layer, and the only symptom is accuracy that stops improving.

Two hosts reading "demo" and getting different data was the ambiguity; the
identity removes it. A host serving a different catalog refuses a round
(record 0007), because the same dataset id names different samples there
and the round would succeed, silently, over the wrong data.

## Why a copy keeps the identity and the keys

A copy is the same corpus on another database, not a new one. Sample ids
are referenced by every annotation, every dataset member and the task
map, so renumbering would silently repoint every task at a different
image. A laptop working offline has to be able to say which catalog its
answers belong to when they are merged back (record 0009). On Postgres,
preserving keys leaves the sequences at zero, so resetting them is the last
thing a copy does — forgetting it is the classic way this fails days later.

## Consequences

- A task map from before identities were recorded is adopted, and the
  caller says so out loud; `push --rebuild-map` settles any doubt by
  matching tasks to samples by blob.
- A run recorded before catalogs had identities carries none, and that
  null is *unknown*, not *some other catalog*: matching it keeps every
  existing history findable, and the scoping tightens on its own as new
  runs arrive. A nullable column added to existing rows means unknown,
  not no.
- A Label Studio project id is per instance and lives in the project's
  state, not in `project.toml`, which is copied between machines where the
  id means nothing. Queues on two machines reconcile through the
  annotations, not the task ids.
- A copy of a catalog numbers its datasets on its own, so a host checks a
  round's dataset name, version and digest, not only its catalog.
