"""Running a package's migration chain from inside its installed wheel.

There is no ``alembic.ini`` anywhere. Each package ships a ``migrations``
directory beside its tables, and everything here takes that directory as
an argument — so the package's own ``schema_version`` is two lines naming
the path and the command, and its ``env.py`` is its database URL and one
call to :func:`run_alembic`.

Two guards on opening a database. ``create_all`` builds the whole schema in
one step, which keeps a checkout runnable and a suite fast, but leaves no
revision recorded; :func:`stamp_if_new` records head against a database
this process just created. A database that already held tables and no
revision predates migrations and is at the *baseline*; :func:`require_current`
refuses it with the commands that fix it, rather than stamping it head and
having it claim columns it does not have.
"""

from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine


class SchemaOutOfDate(Exception):
    """A database whose schema is not the one this code was written against."""


def script_directory(migrations: Path) -> ScriptDirectory:
    """The chain under ``migrations``, read without an ``alembic.ini``."""
    config = Config()
    config.set_main_option("script_location", str(migrations))
    return ScriptDirectory.from_config(config)


def stamp_if_new(engine: Engine, migrations: Path) -> str | None:
    """Record head against a database that has no revision yet.

    **Only correct for a database this process just created.** A database
    that already held tables and no revision predates migrations, and is at
    the baseline rather than at head — stamping it head would have it claim
    columns it does not have, and a later ``upgrade`` would find nothing to
    do. :func:`require_current` is the guard for that case.

    Returns the revision stamped, or None where one was already recorded.
    """
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        if context.get_current_revision() is not None:
            return None
        scripts = script_directory(migrations)
        context.stamp(scripts, "head")
        return scripts.get_current_head()


def require_current(engine: Engine, migrations: Path, name: str) -> None:
    """Refuse a database the code would misread, and say how to fix it.

    ``name`` is the package's short name, so the message can name the
    command that migrates it: ``strata-<name>-migrate``.

    Refused rather than upgraded in passing: a migration rewrites somebody's
    data, and doing that as a side effect of opening a connection is not a
    decision this should be making on their behalf. Refused rather than
    ignored, because the alternative is a missing column surfacing as a
    query error somewhere far from the cause.
    """
    scripts = script_directory(migrations)
    head = scripts.get_current_head()
    with engine.connect() as conn:
        current = MigrationContext.configure(conn).get_current_revision()
    if current == head:
        return
    if current is None:
        raise SchemaOutOfDate(
            f"This {name} predates migrations. Its schema is the baseline, so "
            f"record that and then bring it up to date:\n"
            f"  strata-{name}-migrate stamp {scripts.get_base()}\n"
            f"  strata-{name}-migrate upgrade head"
        )
    raise SchemaOutOfDate(
        f"This {name} is at revision {current}, and the code expects {head}:\n"
        f"  strata-{name}-migrate upgrade head"
    )


def migrate_main(prog: str, migrations: Path, argv: list[str] | None = None) -> None:
    """Alembic's own commands, over one package's chain.

    What a ``strata-<name>-migrate`` script runs: ``upgrade head``,
    ``stamp <revision>``, ``current``, ``history``. The scripts ship inside
    the package, so this works the same from an installed wheel as from a
    checkout. Which database is the ``env.py``'s business.
    """
    import logging

    from alembic.config import CommandLine

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cli = CommandLine(prog=prog)
    options = cli.parser.parse_args(argv)
    if not hasattr(options, "cmd"):
        cli.parser.error("too few arguments")
    config = Config(cmd_opts=options)
    config.set_main_option("script_location", str(migrations))
    cli.run_cmd(config, options)


def run_alembic(context, metadata, url: str) -> None:
    """The body of an ``env.py``: run the chain against ``url``.

    ``context`` is ``alembic.context``, which only exists while alembic is
    executing the environment, so it is passed in rather than imported.
    Batch mode is on for SQLite, which cannot ALTER a column and has the
    table rebuilt instead; on anything else it is harmless and off.
    """
    from logging.config import fileConfig

    from sqlalchemy import engine_from_config, pool

    config = context.config
    if config.config_file_name is not None:
        fileConfig(config.config_file_name)

    if context.is_offline_mode():
        context.configure(
            url=url,
            target_metadata=metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return

    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = url
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=metadata,
            compare_type=True,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


__all__ = [
    "SchemaOutOfDate",
    "migrate_main",
    "require_current",
    "run_alembic",
    "script_directory",
    "stamp_if_new",
]
