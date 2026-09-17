#!/usr/bin/env python3
import argparse
import dotenv
import logging

import flenv
import utils
import wx

logger: logging.Logger = utils.fltools_logger_config()


def handle_qrz(args: argparse.Namespace) -> None:
    logging.info(f"Exporting to QRZ")


def handle_clublog(args: argparse.Namespace) -> None:
    logging.info(f"Exporting To ClubLog")


def handle_wx(args: argparse.Namespace) -> None:
    my_grid: str = flenv.get_env("FLDIGI_MY_LOCATOR")
    logging.info(f"Getting Weather for {my_grid}")
    wx.wx()


def parse_args() -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="fltools", description="Extra macro tools for FLDigi"
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
    args: argparse.Namespace = parse_args()
    dotenv.load_dotenv(utils.FLTOOLS_SCRIPT_DIR / ".test_env")
    args.func(args)


if __name__ == "__main__":
    main()
