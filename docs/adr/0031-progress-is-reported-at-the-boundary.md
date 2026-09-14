# 31. Progress is reported at the boundary, silence is no news, and stopping is asked

**Status:** accepted

## The decision

Long work reports progress through callbacks at the boundary where it is
called. A model accepts `on_epoch` and `on_batch` and may ignore them, but must
accept them. Reports are per epoch and per batch, never per step. An early
stop is a request the model may decline. A job names its stage in words, and
names the expensive stage before it starts. Materialising reports as blobs
land and ticks once at the end even when nothing was fetched.

## Why the boundary

Only the training machine can see training. Across a network the caller sees
nothing until the job ends, so the model reports through the boundary and the
service forwards it. A model that refused the callback would fail ten minutes
in, on the first epoch, which is why the conformance suite calls with one.
Per step would be thousands of updates over the network for a number nobody
reads; per epoch and per batch is what a person watches.

## Why silence is no news

Materialising used to be a hard link and instant. From a bucket it is minutes,
and minutes of silence are indistinguishable from a hang. A version that is
reused fetches nothing and would tick nothing, so a caller kept saying
"materialising" while the GPU ran; the last tick says it is over. A stage
advanced on finish describes the cheap step during the expensive one, so
"training" is reported before training, not after.

## Why stopping is asked

A model that can stop early saves a round; one that cannot should not crash on
being asked. So the stop is a request through `on_epoch`'s return value,
honouring it is optional, and asking is cheaper than not asking and never
wrong.

## Consequences

- Interrupting a remote round stops watching it, not training it, which the
  command says out loud since Ctrl-C usually means the opposite.
- A stage context types its callbacks as callables so a checker sees them
  across the package boundary.
