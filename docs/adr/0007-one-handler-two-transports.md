# 7. One handler, two transports: a round is submitted, not awaited

**Status:** accepted

## The decision

Training and scoring are functions taking a request and a store. The
in-process path and the HTTP service call *those functions*; the service
adds transport and nothing else. A round sent to the modelling host is
submitted and returns a job id; the caller polls. One job runs at a time.
Both sides state a protocol number, checked on `/healthz` before anything
is sent. The client is standard library.

## Why one handler

Validation happens once, an error reads the same locally and remotely, the
suite needs no containers, and the boundary cannot rot because both sides
stay exercised. The failure it prevents is something working on a laptop
and returning a 400 against the GPU host.

## Why submitted rather than awaited

Training is minutes, and the caller is a laptop that closes. A connection
held open for the whole run makes the round only as reliable as the
network and the lid. Submitted, the work carries on where the GPU is, and
reconnecting means asking after a job id rather than starting again. So
polling has to be harder to kill than the thing it watches: a network
error while polling is a failed question about a round, not a failed
round, and is retried. The only fatal answers are the host saying the job
failed, or that it never heard of it.

## Why one at a time, refused rather than queued

A second training job on one GPU does not run slower; it runs out of
memory and takes the first one with it.

## Why a protocol number

The laptop and the host are separate releases once the packages are. A
field one side added and the other ignores fails silently — which is how
remote rounds once dropped a project's features. So `/healthz` states the
protocol, the client refuses a host on another before sending anything,
and every other request names it or is refused. The number goes up only
when an older side would misread a newer one; a field added with a
default does not need it.

## What crosses the wire, and what does not

A dataset id and what it names, a model name, parameters, feature
declarations. Not a directory: the host has the index and the bucket, and
shipping it a gigabyte of images it could fetch itself is paying the
network to avoid using the network. Not a file reference to a model: a
path on the caller's machine would either fail confusingly or find a
different file with the same name. Choosing a parent and recording the
run happen on the host, because only the machine holding the checkpoints
can decide which one, or record a path it actually has.

## Consequences

- What is sent is built from the host's own request models, so a field
  renamed on one side fails a test rather than being dropped at the other.
- Jobs are in memory, deliberately: a thread does not survive a restart
  however carefully its record is written. A completed round is in the run
  store, which is the durable half and the one worth recovering.
- The client lives beside the service it speaks to, in `modelling`, so the
  train stage dispatches to a host without knowing what a project is.
- Standard library for the client: a handful of JSON calls, and a
  dependency in the tool people install locally to save twenty lines is a
  poor trade.
