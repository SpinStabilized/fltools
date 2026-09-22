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
import pathlib
import sys
from collections.abc import Sequence
from types import TracebackType
from typing import Any

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
    lands in whatever file the shim redirects to, or nowhere at all. A macro
    key that silently does nothing is the worst failure mode this tool has.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logger.critical("Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))


class PathsAction(argparse.Action):
    """Print every resolved file location and exit."""

    def __init__(self, option_strings: Sequence[str], dest: str, **kwargs: Any) -> None:
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        described: dict[str, pathlib.Path] = paths.describe()
        width: int = max(len(label) for label in described)
        for label, path in described.items():
            flag: str = "" if path.exists() else "  (missing)"
            print(f"{label:<{width}}  {path}{flag}")
        parser.exit()


def console_script() -> pathlib.Path:
    """
    The absolute path of the installed `fltools` executable.

    Derived from sys.executable rather than sys.argv[0]: the console script
    always sits beside the interpreter of the environment it was installed
    into, whereas argv[0] is only ever the name used to invoke it, which is
    wrong the moment anything is reached through a symlink.

    Prefers an equivalent entry on PATH (uv puts one in ~/.local/bin that
    points into its tool store) so the link follows uv's own indirection
    rather than pinning to its internal layout.
    """
    actual: pathlib.Path = pathlib.Path(sys.executable).parent / "fltools"
    for candidate in (pathlib.Path.home() / ".local" / "bin" / "fltools",):
        if candidate.exists() and candidate.resolve() == actual.resolve():
            return candidate
    return actual


class LinkAction(argparse.Action):
    """Symlink this executable into FLDigi's script directory, then exit."""

    def __init__(self, option_strings: Sequence[str], dest: str, **kwargs: Any) -> None:
        super().__init__(option_strings, dest, nargs="?", **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        # nargs="?" yields a str or None, but the base signature is wider, so
        # narrow it explicitly rather than trusting the runtime value.
        target: str | None = values if isinstance(values, str) else None

        scripts_dir: pathlib.Path = (
            pathlib.Path(target).expanduser()
            if target
            else pathlib.Path.home() / ".fldigi" / "scripts"
        )
        source: pathlib.Path = console_script()
        link: pathlib.Path = scripts_dir / "fltools"

        if not source.exists():
            print(f"Cannot find the fltools executable at {source}", file=sys.stderr)
            parser.exit(1)

        # Refuse to destroy anything that is not ours to replace. A symlink we
        # can safely repoint; a real file might be someone's own script.
        if link.exists() and not link.is_symlink():
            print(
                f"{link} already exists and is not a symlink. Move it aside first.",
                file=sys.stderr,
            )
            parser.exit(1)

        scripts_dir.mkdir(parents=True, exist_ok=True)
        link.unlink(missing_ok=True)
        link.symlink_to(source)

        print(f"Linked {link} -> {source}")
        print("Macros can now call it directly, e.g. <EXEC>fltools qrz</EXEC>")
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
        "--link",
        action=LinkAction,
        metavar="DIR",
        default=argparse.SUPPRESS,
        help=(
            "Symlink this executable into FLDigi's script directory "
            "(default ~/.fldigi/scripts), then exit"
        ),
    )

    parser.add_argument(
        "--paths",
        action=PathsAction,
        default=argparse.SUPPRESS,
        help="Show where fltools reads and writes its files, then exit",
    )

    subparsers: argparse._SubParsersAction[argparse.ArgumentParser] = (
        parser.add_subparsers(
            dest="command", required=True, help="Available subcommands"
        )
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
