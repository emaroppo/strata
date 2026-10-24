# 51. A given split can name lists, so a split carried from elsewhere is reproduced

**Status:** proposed; amends record 0024

## The decision

A given split says which samples are held out and which are validation
either by a metadata key's values, as record 0024 has it, or by lists:
`holdout_lists` and `val_lists`, each a list of `name@version` refs to
lists the catalog holds (record 0050). A list's members are fixed on its
side before anything is drawn, under the same rules as a key's: they win
over grouping, count toward the drawn ratio, and are refused against an
inherited side. A key and lists may be given together.

```toml
[[stage]]
use = "dataset"
name = "phishnet-v7"
spec = "specs/emails-v7.toml"
given = { val_lists = ["emails-v7-val@1"] }
```

A version records the lists by their refs, not their members; a list
version never changes, so the ref is the record. A split by key alone is
recorded exactly as before, so versions frozen under 0024 still compare
as identical. A sample two lists put on different sides, or a key and a
list put on different sides, is refused with the count. A listed checksum
that is not among the members is not an error: a list says what was
chosen elsewhere, and a sample may not have arrived.

## Why

Record 0024's key is read off what a corpus arrived with, at ingest. A
split decided after ingest has nowhere to live on the samples: another
catalog's version carried over in a migration, or a published dev set
assembled by hand. The first case is the one that prompted this. The
emails catalog's version 7 is what the published dev numbers are
measured on, and replicating them on the main catalog means validating
on the same 29 messages. The draw cannot reproduce it, since it shuffles
by sample id and ids differ between catalogs.

Writing a key onto the samples instead was rejected. Metadata is
combined from a sample's origins (record 0049), and a split is not
something any origin said; nor should one project's split be visible on
every other project's samples. A list is already the catalog's record of
"what a script chose" (record 0050), versioned and immutable, which is
what a carried split needs.

## Consequences

- `GivenSplit.sides_for` takes each sample's checksum and each named
  list's members beside the metadata. The catalog reads both in the
  freeze's transaction, so the lists are read under the same lock as
  the selection.
- `key` is no longer required; a given split needs a key with at least
  one name, or at least one list.
- A list named in a given split must exist when the freeze runs; a
  missing one is refused by name.
