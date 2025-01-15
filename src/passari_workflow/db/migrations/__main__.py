#!/usr/bin/env python
"""
Script to run alembic migration commands.

Typically called via pas-db-migrate console script.
"""

import os
import sys
from pathlib import Path

from alembic.config import main as alembic_main

ALEMBIC_CFG_DIR = Path(__file__).parent.parent


def main(argv=sys.argv):
    prog = argv[0].rsplit("/", 1)[-1] if argv[0] != __file__ else argv[0]
    os.chdir(ALEMBIC_CFG_DIR)
    alembic_main(prog=prog, argv=argv[1:])


if __name__ == "__main__":
    main()
