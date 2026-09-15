"""What two strata packages need and neither owns.

Each module is importable on its own: :mod:`migrations` for running an
alembic chain from inside an installed wheel, :mod:`database` for opening
an engine tuned for SQLite, :mod:`service` for starting an app from the
environment, :mod:`plugins` for resolving a name through an entry-point
group, and :mod:`canonical` for the JSON form that gets hashed. What
belongs here is needed by at least two packages and names no domain
object. See ``docs/adr/0017``.
"""

#: Every module here is importable on its own, and that is the promise
#: (``docs/adr/0015``).
PUBLIC_MODULES = frozenset(
    {"canonical", "contract", "database", "migrations", "plugins", "service", "stages"}
)
