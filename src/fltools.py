#!/usr/bin/env python3
import argparse
import dotenv
import logging
import logging.handlers
import os
import pathlib

import wx

# Logging Parameters
LOG_FILE: str = "fltools.log"
LOG_MAX_SIZE: int = 1_000_000
LOG_COUNT: int = 3
LOG_ENCODING: str = "utf-8"

# Anchor file paths to the script's own directory rather than the current
# working directory. FLDigi invokes <EXEC> macros with an unpredictable cwd,
# and resolve() follows any symlink to the real location of this file, so the
# log and the lockout live beside the source no matter how it was launched.
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent.parent
# LOCKOUT_PATH = SCRIPT_DIR / LOCKOUT_FILE

# Configure logging to a rotating file (caps log at ~1 MB, keeping up to 3
# old copies) so it doesn't grow too big over all QSOs being logged.
logging.basicConfig(
    handlers=[
        logging.handlers.RotatingFileHandler(
            SCRIPT_DIR / "logs" / LOG_FILE,
            maxBytes=LOG_MAX_SIZE,
            backupCount=LOG_COUNT,
            encoding=LOG_ENCODING,
        )
    ],
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def handle_qrz(args: argparse.Namespace) -> None:
    logging.info(f"Exporting to QRZ")


def handle_cl(args: argparse.Namespace) -> None:
    logging.info(f"Exporting To ClubLog")


def handle_wx(args: argparse.Namespace) -> None:
    my_grid: str = os.getenv("FLDIGI_MY_LOCATOR", "")
    logging.info(f"Getting Weather for {my_grid}")
    wx.wx()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="fltools", description="Extra macro tools for FLDigi"
    )

    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Available subcommands"
    )

    parser_greet = subparsers.add_parser(
        "qrz", help="Send the currently selected FLDigi log entry to QRZ"
    )
    parser_greet.set_defaults(func=handle_qrz)

    parser_calc = subparsers.add_parser(
        "clublog", help="Send the currently selected FLDigi log entry to ClubLog"
    )
    parser_calc.set_defaults(func=handle_cl)

    parser_calc = subparsers.add_parser(
        "wx", help="Get current weather and any alerts from Pirate Weather"
    )
    parser_calc.set_defaults(func=handle_wx)

    args = parser.parse_args()

    return args


def main() -> None:
    args: argparse.Namespace = parse_args()
    dotenv.load_dotenv(SCRIPT_DIR / ".test_env")
    args.func(args)


if __name__ == "__main__":
    main()
