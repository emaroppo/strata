"""What two strata packages need and neither owns.

Three modules, each importable on its own so a consumer pays only for the
one it uses: :mod:`migrations` for running an alembic chain from inside an
installed wheel, :mod:`service` for starting an app from the environment,
and :mod:`plugins` for resolving a name through an entry-point group.

The rule for what belongs here: needed by at least two packages, and
naming no domain object. A catalog, a run or a label is never mentioned.
"""
