# 6. A prediction is a function of three inputs, and nothing is ever invalidated

**Status:** accepted

## The decision

The prediction cache is keyed on the run, the sample's checksum, and a
digest of the features the model was told. Nothing in it is ever
invalidated. It lives beside the runs, on the machine that did the work.

## Why a cache at all

Ranking a review queue needs a score for every unlabelled sample, not just
the ones about to be shown — least-confident-first cannot pick a top 200
without having looked at all of them. That is a full inference pass per
push, minutes of GPU, and asking again from the same checkpoint pays for
an identical answer.

## Why nothing is invalidated

It is a property rather than an omission. A prediction is a function of a
checkpoint and some bytes, and both are immutable: a run writes its
checkpoint once, and blobs are addressed by content. An entry keyed on
both cannot go stale; the only reason to drop one is disk.

## Why the third input went into the key

A feature is another label set's answer, under review by whoever owns it,
so a correction is the ordinary case rather than the exception. Keyed on
the first two inputs alone, the cache survived a correction to the third
and served answers for inputs that no longer existed. Widening the key is
what let the stated property stay literally true: a corrected feature is a
miss, and the old row remains the right answer for the inputs it was
computed from. The digest is empty for a project declaring no features,
so every row written before it existed reads exactly as before.

The digest lives in `labels` because two hosts compute it and a third
stores it: the laptop keys its lookups with it, the modelling host its
answers. A digest that differed between them would not be wrong, only a
cache that never hits — which is why its test pins its output rather than
its properties.

## Consequences

- The cache is beside the runs because a run id means something only
  within one store (record 0005), and on the machine that worked because
  the answer is the same for every caller: a client-side cache would help
  only whoever asked first.
- Keyed on the checksum rather than a sample id (record 0001): the bytes
  are what the model saw.
- It holds whatever a model produced — choices, spans, boxes — and reads
  it back through the discriminator. Pinning it to one type would make a
  cache that quietly refuses, or mangles, every task type but the first.
- The training core returns predictions and never writes them; persisting
  is the caller's business, or a catalog dependency comes back into the
  core.
- What a scoring pass returns holds a prediction rather than being one.
  When both were called prediction, code unwrapped the value in some places
  and not others, and the cache stored wrappers. A wrapper serialises
  happily and reads back empty, since pydantic ignores keys it does not
  know, so a cache full of nothing looks exactly like a cache full of
  answers until a ranking sorts on them. The cache refuses anything that is
  not model output.
- When spans went from one `label` to a list of `labels`, the cache was
  rewritten to follow, so a cached answer keeps reading under the one form
  the value type accepts and nothing computed was thrown away.
