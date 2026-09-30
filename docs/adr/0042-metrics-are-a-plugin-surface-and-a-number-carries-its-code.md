# 42. Metrics are a plugin surface, and a number carries the identity of the code that produced it

**Status:** accepted; amends record 0035

## The decision

A task, what is being achieved and how getting it right is counted, and a
failure mode, one way of getting it wrong, are plugins. Each is a class
with a name and a version, found by name through an entry point group
(`strata.evaluation_tasks`, `strata.failure_modes`) or from a project's
own `file.py:Class`, as a model is (record 0034). Every score records the
identity of the code that produced it: its name, its declared version, and
its source, `<distribution>==<version>` for an installed package or
`file:<path>#sha256:<digest>` for a file. The identities are in the
evaluate stage's request, so they are in its key.

A comparison is sound between scores of one identity. That replaces the
roadmap's position that metrics are not a plugin surface at all.

## Why

The position was right about what it protected and wrong about the cost.
A pluggable metric does let two numbers be computed by different code and
compared as if they were not; closing the surface prevented that by
allowing one implementation. On the emails project it prevented the work
instead. Anonymisation fails in ways no first-party metric named, entity
fragmentation first among them, and the ways found only by looking at
output: each new one meant a package release before it could be counted,
and some belong to one corpus and no other.

What makes a comparison mean something is not that the code is
first-party but that it is the same code. Recording which code ran keeps
that property with the surface open: a score from an edited file carries a
new digest, a comparison across it can be refused by name, and a rerun
after the edit scores again because its key changed.

## Why the file's bytes, not its declared version

A project's own file is edited while someone is looking at output, and
nobody bumps a version for an experiment. The bytes are the version that
means something. An installed package's version stands for its bytes,
which is why it is used there instead. A file's path in a key is made
relative to the project, as every other path is (record 0037), so a moved
project keeps its keys.

## Why a failure mode must bring an example

Open membership invites overlap: a new mode measuring what an existing one
does double-counts one failure as two. Each mode carries the case it
exists for, and the conformance suite holds it to raising that mode and no
isolated first-party mode outside the ones it declares it co-occurs with.
An overlapping mode fails there, naming the one it overlaps, before it can
distort a table.

## Consequences

- `strata-evaluation` depends on `strata-common` for the resolver.
- The evaluate stage resolves and checks every task and failure mode
  against the label set before a prediction is made, and refuses code that
  changed between a request being made and it running.
- Scoring runs on the caller, whichever host predicted, so a project's own
  file needs nothing from a modelling host.
- An experiment file names tasks as tables with `use`; editing a project's
  own task or failure mode reruns evaluate alone.
- A `compare` that refuses scores of different identities is still to come.
