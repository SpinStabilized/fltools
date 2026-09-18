# -*- coding: utf-8 -*-
import logging
import logging.handlers

from typing import Final

from fltools import paths

FLTOOLS_LOGGER_ID: Final[str] = "fltools"

FLTOOLS_LOG_MAX_SIZE: Final[int] = 1_000_000
FLTOOLS_LOG_COUNT: Final[int] = 3
FLTOOLS_LOG_ENCODING: Final[str] = "utf-8"

FLTOOLS_USER_AGENT: Final[str] = "fltools/0.1.0 (N3BMC)"


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

    paths.ensure_dirs()

    file_handler: logging.handlers.RotatingFileHandler = (
        logging.handlers.RotatingFileHandler(
            paths.LOG_FILE,
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
