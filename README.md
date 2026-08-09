# Pick up here

Written at the end of the second day, once the loop was running across three
machines. Delete this when it goes stale — it is a handoff, not
documentation.

## Where things stand

On `main`, working tree clean, everything pushed, **816 tests passing**,
ruff clean. `main` now carries the whole workspace; the branch that held it
is merged.

The loop runs end to end, distributed:

```
ingest → push → (review in Label Studio) → export → train
```

- **The catalog host** holds the index (Postgres) and the blobs (tar shards
  in S3-compatible storage), plus the blob server that hands Label Studio
  signed URLs.
- **The GPU host** runs the modelling service under a systemd user unit. It
  takes a dataset id, materialises it against its own cache, trains, and
  records the run. Rounds are submitted, not awaited.
- **Any machine** can drive it: the CLI needs no ML framework, since torch
  arrives with the baselines on whoever trains.

A full round has been through this from a machine holding none of the data:
pushed with pre-annotations scored on the GPU host, reviewed in a browser
against images served over HTTP, exported to the shared catalog, and trained
from a submitted job — interrupted at the client mid-round and reattached
to, which is the property the submit-and-poll shape exists for.

## Start here

**1. Archive both run stores, then train.** Run ids are timestamps and
hosts now, and there is no migration — an integer and a timestamp sort
against each other by their first digit. The store says so and gives the
command:

    mv projects/<name>/runs/runs.db{,.archived}      # and the same on the GPU host

Then `train --fresh`. The trap that made the numbers unreadable is fixed:
`--fresh` was a request while being cold was an outcome, and the parameters
keyed off the request, so a cold run trained on an increment's schedule.
Three of the four early runs were cold on four epochs and landed near 0.90;
the one that got its longer schedule reached 0.9200. The question of whether
warm starting helps has not actually been asked yet.

**2. Containers for the GPU host**, if you want them. Everything else in
Phase 8 is done, so this is packaging a service that already works.

Setting a machine up takes one file from the project directory —
`project.toml`; the rest is data, checkpoints and materialised versions,
tens of gigabytes of it — plus `config.toml`, `scripts/secrets.sh` and the
key database. No ML framework, since torch arrives with the baselines on
whoever trains. Then `init` gives that machine its own queue, and the two
reconcile through the annotations rather than through task ids.

## What is open

**The merge.** Everything it needs now exists — a catalog identity that a
copy carries, run ids that cannot collide, and somewhere to put
disagreements — and nothing calls `record_conflict`. Folding a local
catalog into the main one is the piece that makes offline work real.

**Two run stores.** No longer ambiguous, just separate: `report` on a laptop
sees only the local one. Reading a remote store through `GET /runs/{id}` is
the smaller half and worth doing before the merge.

**Nothing records which catalog a run trained against.** The identity exists;
no run carries it.

The rest is in `roadmap.md` under *Loose ends*.

## Things worth knowing before changing anything

**A run is submitted, not awaited.** Losing the network does not reach the
training; polling retries and reports. But `systemctl --user restart` kills
an in-flight round — jobs live in memory.

**One job at a time, refused rather than queued.** Two on one GPU do not run
slower, they run out of memory and take the first with them. So a push that
scores a pool cannot run during a round.

**Blob caches are content-addressed and shared.** The CLI and the modelling
service both read and write the same directories. Both write through a
temporary name, because a short file at the address of a whole one is served
as a hit forever and nothing rehashes a cache entry.

**Nothing invalidates a prediction.** A checkpoint and some bytes give one
answer, and both are immutable. If a cache ever holds something wrong, it
holds it until deleted.

**Task URLs are signed and expire.** Thirty days. A queue older than that
stops loading images; `relink` re-signs. It also moves tasks between the
local mount and the serving API.

## The day's larger lesson

Most of what went wrong was found by looking rather than by failing: a
command reading a stale index, task URLs keyed on where bytes live rather
than what they are, a row that could not be hashed once it carried
metadata, a job reporting the wrong stage for an entire training run. None
raised an error. Each showed up as a number quietly wrong, or a label that
did not match what the machine was doing.

The format-generality faults were the same shape — nothing failed, a
catalog simply could not hand back what it had been given.

The exception is `push`, which broke three times loudly and always on
someone else's machine: a stale import after a module moved, a type
mismatch between the cache and the local handler, and a run passed around
as a dict that two lines still read as an object. It is the one part of the
loop with no test that drives it, because doing so needs a stand-in for the
Label Studio client. That is in `TODO.md`, and it is where the next bug
will be.
