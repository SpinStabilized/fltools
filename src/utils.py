# -*- coding: utf-8 -*-
import logging
import logging.handlers
import pathlib

from typing import Final

# Anchor file paths to the script's own directory rather than the current
# working directory. FLDigi invokes <EXEC> macros with an unpredictable cwd,
# and resolve() follows any symlink to the real location of this file, so the
# log and the lockout live beside the source no matter how it was launched.
FLTOOLS_SCRIPT_DIR: Final[pathlib.Path] = pathlib.Path(__file__).resolve().parent.parent

FLTOOLS_LOGGER_ID: Final[str] = "fltools"

FLTOOLS_LOG_DIR: Final[pathlib.Path] = pathlib.Path(FLTOOLS_SCRIPT_DIR / "logs")
FLTOOLS_LOG_FILE: Final[pathlib.Path] = pathlib.Path(
    FLTOOLS_LOG_DIR / f"{FLTOOLS_LOGGER_ID}.log"
)
FLTOOLS_LOG_MAX_SIZE: Final[int] = 1_000_000
FLTOOLS_LOG_COUNT: Final[int] = 3
FLTOOLS_LOG_ENCODING: Final[str] = "utf-8"

FLTOOLS_USER_AGENT: Final[str] = 'fltools/0.1.0 (N3BMC)'

def fltools_logger_config(level: int = logging.INFO) -> logging.Logger:
    """Configure the fltools' logger

    Parameters
    ----------
    level
        The debugging level, should probably use constants from the
        `logging` module.

    """
    logger: logging.Logger = logging.getLogger(FLTOOLS_LOGGER_ID)
    logger.setLevel(level)
    log_format: logging.Formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    FLTOOLS_LOG_DIR.mkdir(parents=True, exist_ok=True)

    file_handler: logging.handlers.RotatingFileHandler = (
        logging.handlers.RotatingFileHandler(
            FLTOOLS_LOG_FILE,
            maxBytes=FLTOOLS_LOG_MAX_SIZE,
            backupCount=FLTOOLS_LOG_COUNT,
            encoding=FLTOOLS_LOG_ENCODING,
        )
    )
    file_handler.setFormatter(log_format)
    logger.addHandler(file_handler)
    return logger


def get_fltools_logger() -> logging.Logger:
    """Grab a FLTools Logger"""
    return logging.getLogger(FLTOOLS_LOGGER_ID)
