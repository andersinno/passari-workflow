"""
Test Alembic migrations
"""
import os
from contextlib import contextmanager
from os import fspath
from pathlib import Path
from typing import Iterator

from alembic import command
from alembic.config import Config

import passari_workflow.db
from passari_workflow.db.models import Base

DB_PATH = Path(passari_workflow.db.__file__).parent


def test_migrate(session, engine, database):
    """
    Test migrations by running all migrations and then downgrading
    """
    config = Config(fspath(DB_PATH.resolve() / "alembic.ini"))

    try:
        Base.metadata.drop_all(engine)

        with run_in_path(DB_PATH):
            # Upgrade the database
            command.upgrade(config, "head")

            # Downgrade the database
            command.downgrade(config, "base")
    finally:
        # Ensure that the tables are the same after the test, even if
        # something fails
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)


@contextmanager
def run_in_path(path: Path) -> Iterator[None]:
    orig_cwd = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(orig_cwd)
