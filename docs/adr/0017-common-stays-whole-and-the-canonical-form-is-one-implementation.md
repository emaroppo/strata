# 17. `common` stays whole, and the canonical form is one implementation

**Status:** accepted

## The decision

`strata-common` keeps its six modules behind their extras: the store
plumbing catalog and modelling share, and the identity vocabulary every
tool shares. The canonical JSON form that gets hashed has one
implementation, in `common`, and `strata-post-process` and
`strata-feature-store` import it rather than re-declaring it. `common`
ships one payload, `strata.common.contract.PAYLOAD`, and every package
that hashes anything pins the digest of that payload in its own tests.

## Why not split it

Any change to `common` is a release into every consumer, and the two
halves have nothing to do with each other, so a change to the migration
runner ships to a package that only hashes specs. The alternative was to
split the store plumbing from the identity vocabulary, or to copy the
small modules into their consumers. Both trade a coordinated release for
copies that drift, and drift in plumbing is the worse of the two: it is
silent, it accumulates, and the day it matters is the day a migration
runs differently on two hosts. A coordinated release is visible and
happens on purpose.

## Why one implementation of the hash

Three copies of the canonical rules existed, and two of them disagreed:
one wrote a whole-second timestamp with microseconds and the other did
not, so the same spec hashed differently in two tools. The argument for
re-declaring was that no release of one tool should be coordinated with
another; that argument held between two producers of data, and `common`
is not a producer. It names no domain object, and a hashing rule is the
one thing every tool has to agree on exactly.

## Why the digest is pinned by each consumer

If `common` shipped the digest, a consumer's test would compare the
library to itself. The payload is shared and the pin is the consumer's,
so a change to the rules upstream fails in each consumer on upgrade,
before it moves a stored identity. The digest was computed by
post-process's own implementation before it imported `common`, so the
first pin is a second implementation's word.

## Consequences

- `CANONICAL_VERSION` moves when the rules change meaning, and every
  consumer's pin fails with it. That is a coordinated release, taken
  knowingly.
- The sister repositories take `common` as a path source beside them
  until the split publishes it, and as a versioned dependency after.
- `hash_file` lives in `common` too: both sisters carried the same one.
