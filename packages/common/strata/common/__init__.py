"""What two strata packages need and neither owns.

Each module is importable on its own, so a consumer pays only for the one
it uses: :mod:`migrations` for running an alembic chain from inside an
installed wheel, :mod:`database` for opening an engine tuned for SQLite,
:mod:`service` for starting an app from the environment, :mod:`plugins`
for resolving a name through an entry-point group, and :mod:`canonical`
for the JSON form that gets hashed.

The rule for what belongs here: needed by at least two packages, and
naming no domain object. A catalog, a run or a label is never mentioned.
"""

#: Every module here is importable on its own, and that is the promise
#: (``docs/adr/0015``).
PUBLIC_MODULES = frozenset(
    {"canonical", "contract", "database", "migrations", "plugins", "service", "stages"}
)
