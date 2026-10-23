# 46. Preparation is a chain of stages, declared in a spec

**Status:** proposed; amends records 0040 and 0033, and departs from
record 0037 for preparation's stages only

## The decision

A prepare run (record 0045) is declared in a TOML spec. The spec gives:

- an ordered chain of **stages**;
- the collection and type it writes.

Which files a run prepares is not in the spec. The run is handed a list
of them (record 0045).

A stage does two things, and only these:

- it records facts about the occurrence it reads, such as a message's
  headers or a frame's index;
- it changes the body, as cleaning does.

A stage never writes an annotation. Labels on prepared samples come
from runs of their own (record 0048).

The design is strata-post-process's, applied to samples. A stage
declares the kind of item it accepts and the kind it produces, and the
chain is checked before anything is read. Each stage's parameters are a
model of their own. Stages are split by cardinality into transforms,
filters and splits. The chain runs on each input, in memory, and only
what its last stage produces is stored. No stage learns from the corpus.
Stages are plugins, registered under `strata.prepare_stages`.

## What this amends, and why

- **Record 0040: a preparer is no longer one opaque step.**
  `Preparer.prepare(source, out_dir, *, root)` hid everything a
  preparation does inside one call. Its intermediate steps could not be
  checked one at a time, and the rules it applied were not part of any
  record. A preparer becomes a chain of stages. Today's preparers run as
  a chain of one stage until they are ported, so nothing breaks on the
  day this lands.
- **Record 0033: the contract checks a chain, and the spec is inside the
  determinism it checks.** The suite already checks that a preparer
  gives the same bytes from the same source. A chain's output also
  depends on its parameters and rule files. So "the same source" becomes
  "the same input under the same spec".
- **Record 0037: preparation's stages are plugins, not a table.** Record
  0037 keeps experiment stages in a hand-maintained table until a third
  implementation exists, and that still holds for experiments.
  Preparation already has its implementations outside strata: preparers
  are plugins (records 0033, 0040), and stages ship with `prepare-email`,
  `prepare-video` and project packages. A table inside strata could not
  list them.

## Why a stage changes the body or records facts, and never labels

A label on a sample is an answer, and an answer has a source that ranks
it (record 0009). If a stage wrote one, a preparation would be giving
answers. They would carry no source of their own, and they would be
redone every time the chain ran. Phishnet's footer removal shows the
difference. Removing a footer from the body was a decision made at
preparation. Marking it as a span would be a label, and so it is
written over the prepared samples, by an import run with its run id
(record 0048). A later model can then replace the rules without
preparing anything again.

## Why a chain, and why post-process's design

Phishnet's cleaning shows why one opaque step is not enough. It runs as
loading, then body cleaning, then footer removal. Moving it onto strata
means checking it one step at a time:

- the parsing against the bodies phishnet loaded;
- the cleaning against the bodies phishnet kept.

Its rule files change what comes out, so they have to be part of what a
run records.

Strata-post-process solved the same problem for tables, and preparation
takes its design for the `sample` unit. Post-process lists that unit as
expressible but not built, because it needs a content-addressed store
to read from. The catalog is that store.

| Post-process | Preparation |
|---|---|
| A pipeline file: input, declared fields, ordered stages | A TOML spec: ordered stages, an output collection and type. The files come with the run. |
| Only the frame and its schema pass between stages | Only the item and its kind pass between stages. An item is the body plus the facts recorded about its occurrence. |
| Fields declare kinds; stages declare what they accept; checked at load | Kinds such as `bytes`, `text` and `image` are core, and a plugin adds its own, such as `mail`. A misordered chain fails `validate`, which reads no data. The last stage must produce the declared output type. |
| Params are a model per stage; an unknown key is an error | The same |
| Stages and rules are disjoint by cardinality | **Transforms** (one in, one out), **filters** (one in, none or one out, counted), **splits** (one in, many out) |
| A run directory: canonical spec, manifest | A run row in the catalog: canonical spec, stage versions, rule-file digests, the file list's digest, counts |

TOML rather than post-process's JSON, so that a prepare spec reads like
an experiment file. Either way it is canonical JSON that is hashed
(record 0017).

## Why only the last stage is stored

The chain runs on each input, in memory, and only its last stage's
output is stored. Phishnet stored every stage and overwrote its own
inputs, and that is why its corpora can no longer be explained.

A stage output that is a sample in its own right comes from a prepare
run of its own, whose input is samples. A local cache of stage outputs
is allowed for developing a chain. It is keyed by input checksum and by
the chain up to that stage, and it is never a record.

## Why no stage learns from the corpus

Post-process has `fit` because a statistic is learned over many rows. A
preparation stage that learned would make a sample's bytes depend on the
other files beside it. That breaks preparing one input at a time, and
with it content addressing. Deduplication is the catalog's job, by
checksum.

## What a spec looks like

```toml
name = "enron-single"

[[stage]]
name = "parse-rfc822"         # the body, and every header

[[stage]]
name = "clean-debris"         # quoted-printable debris, quote prefixes

[output]
collection = "phishnet/enron/single"
type = "email"
```

It is run on a list of files:

```bash
strata-catalog prepare specs/enron-single.toml --files list.txt
```

Defaults are materialised before hashing, as in record 0037: an omitted
field and a written default give the same spec. A rule file a stage
reads is hashed by content into the spec.

## Consequences

- **`strata-prepare` gains the stage engine, the spec model and the
  stage contract,** with two commands that read no catalog: `validate
  <spec>` and `stages`. The catalog runs the engine (record 0047).
- **A name registered twice under `strata.prepare_stages` is refused,**
  as a preparer is (record 0033).
- **`prepare-email` becomes stages:** `parse-rfc822`, `parse-message-json`
  and `clean-debris`. Marking disclaimers and footers moves out of
  preparation, into an import run in the project that uses it.
- **The folder preparers and `prepare-video`** run as one-stage chains
  until they are ported.
