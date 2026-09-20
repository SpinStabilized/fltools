#!/usr/bin/env python3
"""
Command line entry point for fltools.

Subcommands are the things you put on an FLDigi macro key. Anything that
exists for the operator rather than for a macro (diagnostics, version
reporting) is a top-level flag, so that the subcommand list stays a list of
macro verbs.
"""

import argparse
import logging
import sys
from types import TracebackType

import dotenv

from fltools import __version__, clublog, flenv, paths, qrz, utils, wx

logger: logging.Logger = utils.fltools_logger_config()


def log_uncaught(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: TracebackType | None,
) -> None:
    """
    Route any unhandled exception into the rotating log.

    Without this, a traceback goes to stderr, which under FLDigi means it
    lands in whatever file the bash utility redirects to, or nowhere at all. A macro
    key that silently does nothing is the worst failure mode this tool has.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))


class PathsAction(argparse.Action):
    """Print every resolved file location and exit."""

    def __init__(self, option_strings, dest, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None) -> None:  # type: ignore[no-untyped-def]
        described = paths.describe()
        width = max(len(label) for label in described)
        for label, path in described.items():
            flag = "" if path.exists() else "  (missing)"
            print(f"{label:<{width}}  {path}{flag}")
        parser.exit()


def handle_qrz(args: argparse.Namespace) -> None:
    logger.info("Exporting to QRZ")
    qrz.qrz()


def handle_clublog(args: argparse.Namespace) -> None:
    logger.info("Exporting To ClubLog")
    clublog.clublog()


def handle_wx(args: argparse.Namespace) -> None:
    my_grid: str = flenv.get_env("FLDIGI_MY_LOCATOR")
    logger.info(f"Getting Weather for {my_grid}")
    wx.wx()


def parse_args() -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="fltools", description="Extra macro tools for FLDigi"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Show the fltools version and exit",
    )

    parser.add_argument(
        "--paths",
        action=PathsAction,
        default=argparse.SUPPRESS,
        help="Show where fltools reads and writes its files, then exit",
    )

    subparsers: argparse._SubParsersAction = parser.add_subparsers(
        dest="command", required=True, help="Available subcommands"
    )

    parser_qrz: argparse.ArgumentParser = subparsers.add_parser(
        "qrz", help="Send the currently selected FLDigi log entry to QRZ"
    )
    parser_qrz.set_defaults(func=handle_qrz)

    parser_clublog: argparse.ArgumentParser = subparsers.add_parser(
        "clublog", help="Send the currently selected FLDigi log entry to ClubLog"
    )
    parser_clublog.set_defaults(func=handle_clublog)

    parser_wx: argparse.ArgumentParser = subparsers.add_parser(
        "wx", help="Get current weather and any alerts from Pirate Weather"
    )
    parser_wx.set_defaults(func=handle_wx)

    args: argparse.Namespace = parser.parse_args()

    return args


def main() -> None:
    sys.excepthook = log_uncaught

    args: argparse.Namespace = parse_args()

    # load_dotenv returns False for a missing file rather than raising, so an
    # unreported miss shows up later as "QRZ_KEY is not set" while a perfectly
    # good .env sits somewhere else entirely. Run `fltools --paths` to see
    # where this is looking.
    if not dotenv.load_dotenv(paths.ENV_FILE):
        logger.warning(f"No .env loaded from {paths.ENV_FILE}")

    args.func(args)


if __name__ == "__main__":
    main()
