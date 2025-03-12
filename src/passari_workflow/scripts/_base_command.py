import copy
import logging
import sys

import click

_VERBOSITY_PARAMS = [
    click.Option(["-v", "--verbose"], count=True, help="Increase verbosity"),
    click.Option(["-q", "--quiet"], count=True, help="Decrease verbosity"),
]


class BaseCommand(click.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params.extend(_VERBOSITY_PARAMS)

    def invoke(self, ctx):
        new_ctx = copy.copy(ctx)
        del new_ctx.params["verbose"]
        del new_ctx.params["quiet"]
        return super().invoke(new_ctx)

    def parse_args(self, ctx, args):
        result = super().parse_args(ctx, args)
        main_logger = logging.getLogger(self.callback.__module__)

        verbosity = ctx.params.get("verbose", 0)
        quiet = ctx.params.get("quiet", 0)
        verbosity -= quiet
        self.setup_logging(main_logger, verbosity)
        return result

    def setup_logging(
        self,
        main_logger: logging.Logger,
        verbosity: int = 0,
    ) -> None:
        """
        Setup logging based on the verbosity level.

        The main_logger and root logger levels will be set according to
        the following table:

            verbosity | main_logger | root logger
            -------------------------------------
            <= -3     | ERROR       | ERROR
            -2        | WARNING     | ERROR
            -1        | WARNING     | WARNING
            0         | INFO        | WARNING
            1         | INFO        | INFO
            2         | DEBUG       | INFO
            >= 3      | DEBUG       | DEBUG

        Handlers will be created for stdout and stderr. INFO and DEBUG
        messages will be printed to stdout, WARNING and higher will be
        printed to stderr only (not to stdout).
        """
        clamped_verbosity = min(max(verbosity, -3), 3)
        main_logger_level, root_logger_level = {
            -3: (logging.ERROR, logging.ERROR),
            -2: (logging.WARNING, logging.ERROR),
            -1: (logging.WARNING, logging.WARNING),
            0: (logging.INFO, logging.WARNING),
            1: (logging.INFO, logging.INFO),
            2: (logging.DEBUG, logging.INFO),
            3: (logging.DEBUG, logging.DEBUG),
        }[clamped_verbosity]
        main_logger.setLevel(main_logger_level)
        logging.root.setLevel(root_logger_level)

        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(logging.Formatter("%(message)s"))
        stdout_handler.setLevel(logging.DEBUG)
        stdout_handler.addFilter(UpperLevelLogFilter(logging.INFO))

        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.WARNING)
        stderr_handler.setFormatter(
            logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
        )

        # Replace the existing root logger handlers with the new ones
        for handler in logging.root.handlers:
            logging.root.removeHandler(handler)
        logging.root.addHandler(stdout_handler)
        logging.root.addHandler(stderr_handler)


class UpperLevelLogFilter(logging.Filter):
    def __init__(self, max_level: int):
        super().__init__()
        self.max_level = max_level

    def filter(self, record):
        if record.levelno <= self.max_level:
            return True
        return False
