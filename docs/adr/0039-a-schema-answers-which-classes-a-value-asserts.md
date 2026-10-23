# 39. A schema answers which classes a value asserts, and the catalog indexes nothing else

**Status:** accepted; extended by record 0050 (proposed)

## The decision

Every label schema implements one indexing contract, `classes_asserted`. On
every write the catalog derives `annotation_class` rows through it, and every
question of the form "which samples are labelled X" is a join on that table.
The catalog reads no annotation payload to answer a query. On a copy the
index is copied, not recomputed.

## Why

Annotations are stored whole, as the value type serialises them (record 0006),
and their shape is the label set's business (record 0014). Without a contract
the catalog would have to understand each shape to query it, which is how a
detector's boxes once read back as empty choices. With one, a new label type is
queryable the day it exists, from a single method on its schema, and the
catalog has learned nothing about it. Reading `values` as class names is true
only for classification; for spans they are objects that do not even compare,
which is why the contract is a method and not a convention.

## Why copied and not recomputed

Recomputing the index on `copy` would mean `copy` knowing what a value means,
which is exactly the knowledge the contract keeps out of the catalog.

## Consequences

- `with_class` is the join the index exists for, and the per-class counts in
  `stats` double as a check that indexing did its job.
- Which classes a value asserts is also how a pull refuses undeclared labels
  before writing, and how a label set is widened by the classes in use.

## Amendments

- **The class index is kept for every answer, not only the current one
  (record 0050, proposed).** It was rewritten on each write, so the
  classes a superseded answer asserted were gone. Running a version's
  selection spec again needs them as they stood when it was frozen. The
  index is derived exactly as before, and keyed by the annotation row.
