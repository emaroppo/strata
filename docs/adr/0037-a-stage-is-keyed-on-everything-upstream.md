# 37. A stage is keyed on everything upstream, and a record is never invalidated

**Status:** accepted

## The decision

An experiment file's canonical JSON is hashed, and the hash is its identity.
A stage's key is the spec through that stage with the grid excluded, the
implementation's version, the request made portable, and the catalog's
identity. The project is in the hash by its declared identity, never by the
locator used to find it. A stage whose key has a record in the ledger is
handed downstream as if it had run, parsed back into its model. Nothing is
invalidated: a change moves every key after it. The chain is checked before
anything runs. A grid runs every trial cold or from one named parent. Stages
are a hand-maintained table.

## Why JSON, and why canonical

The argument for JSON is not that it is declarative but that it hashes. A spec
that cannot be canonically serialised cannot be an identity, and a changed
spec that hashes the same silently reuses what the old one produced. So
defaults are materialised before hashing, an omitted field and a written
default agreeing, and a trial's hash is over the effective config, so two
overrides are two identities (record 0017 has the rules).

## Why everything upstream is in the key

The request is in the key so an edit to `project.toml` or a rerun upstream
moves it rather than reusing a record made under other inputs. The
implementation's version is in it because a changed implementation under an
unchanged spec is a different result (record 0005 says the same of models).
The catalog's identity is in it so a record is never handed to another
catalog (record 0008). The grid is out of the prefix so trials that agree
through a stage share its record, and only the varied stages run per trial.

## Why identity, not locator

The same file beside the same project is the same experiment on any machine;
the path used to find the project is not part of what it is, so the project's
identity is bound at load and the locator never enters the hash. An
unfindable project is refused at load.

## Why the chain is checked first

Every kind a stage consumes must be produced earlier. Walking the chain like a
schema through a pipeline fails at load rather than an hour in; a kind meeting
the wrong record type is a wiring error named at the stage rather than an
attribute error later.

## Why a grid is cold or from one parent

Warm-starting each trial from the previous one makes the results depend on the
order the trials ran, which is the one thing a grid must not do. This rule
lived only in an error string before this record.

## Why a table and not a plugin group

There is no third-party stage. A plugin seam is designed at the third
implementation, not the first; until then a hand-maintained table says
exactly what can run and nothing shells out to a command.

## Consequences

- Parameters layer: the project's, the file's overrides, a grid key on top. A
  file naming another model than the project's starts from nothing, since the
  project's parameters were written for its own.
- A reused record and a fresh one are the same object downstream.
