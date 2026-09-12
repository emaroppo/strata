"""The migration plumbing, against a two-revision chain written for the test."""

import textwrap
from pathlib import Path

import pytest
from alembic.runtime.migration import MigrationContext
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect

from strata.common.migrations import (
    SchemaOutOfDate,
    migrate_main,
    require_current,
    script_directory,
    stamp_if_new,
)

metadata = MetaData()
Table("thing", metadata, Column("id", Integer, primary_key=True), Column("note", String))

#: A chain of two: the baseline makes the table, the head adds a column.
ENV = """
import os

from alembic import context
from sqlalchemy import Column, Integer, MetaData, String, Table

from strata.common.migrations import run_alembic

metadata = MetaData()
Table("thing", metadata, Column("id", Integer, primary_key=True), Column("note", String))

run_alembic(context, metadata, os.environ["STRATA_TEST_URL"])
"""
BASE = """
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("thing", sa.Column("id", sa.Integer, primary_key=True))


def downgrade():
    op.drop_table("thing")
"""
HEAD = """
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("thing") as batch:
        batch.add_column(sa.Column("note", sa.String))


def downgrade():
    with op.batch_alter_table("thing") as batch:
        batch.drop_column("note")
"""


@pytest.fixture
def migrations(tmp_path) -> Path:
    root = tmp_path / "migrations"
    (root / "versions").mkdir(parents=True)
    (root / "env.py").write_text(textwrap.dedent(ENV))
    (root / "script.py.mako").write_text("")
    (root / "versions" / "0001_base.py").write_text(textwrap.dedent(BASE))
    (root / "versions" / "0002_head.py").write_text(textwrap.dedent(HEAD))
    return root


@pytest.fixture
def url(tmp_path) -> str:
    return f"sqlite:///{tmp_path / 'thing.db'}"


def _revision(url: str) -> str | None:
    with create_engine(url).connect() as conn:
        return MigrationContext.configure(conn).get_current_revision()


def test_the_chain_is_read_without_an_ini(migrations):
    scripts = script_directory(migrations)
    assert scripts.get_base() == "0001"
    assert scripts.get_current_head() == "0002"


def test_a_fresh_database_is_stamped_at_head_once(migrations, url):
    engine = create_engine(url)
    metadata.create_all(engine)
    assert stamp_if_new(engine, migrations) == "0002"
    assert stamp_if_new(engine, migrations) is None
    assert _revision(url) == "0002"


def test_a_current_database_passes(migrations, url):
    engine = create_engine(url)
    metadata.create_all(engine)
    stamp_if_new(engine, migrations)
    require_current(engine, migrations, "thing")


def test_tables_without_a_revision_are_refused_with_the_fix(migrations, url):
    engine = create_engine(url)
    metadata.create_all(engine)
    with pytest.raises(SchemaOutOfDate, match="strata-thing-migrate stamp 0001"):
        require_current(engine, migrations, "thing")


def test_a_database_behind_head_names_the_upgrade(migrations, url):
    engine = create_engine(url)
    metadata.create_all(engine)
    with engine.begin() as conn:
        MigrationContext.configure(conn).stamp(script_directory(migrations), "0001")
    with pytest.raises(SchemaOutOfDate, match="(?s)at revision 0001.*upgrade head"):
        require_current(engine, migrations, "thing")


def test_migrate_main_runs_the_chain_through_the_env(migrations, url, monkeypatch):
    monkeypatch.setenv("STRATA_TEST_URL", url)
    migrate_main("strata-thing-migrate", migrations, ["upgrade", "head"])
    assert _revision(url) == "0002"
    columns = {c["name"] for c in inspect(create_engine(url)).get_columns("thing")}
    assert columns == {"id", "note"}


def test_migrate_main_without_a_command_is_a_usage_error(migrations):
    with pytest.raises(SystemExit) as raised:
        migrate_main("strata-thing-migrate", migrations, [])
    assert raised.value.code == 2
