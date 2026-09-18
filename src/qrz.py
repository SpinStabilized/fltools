"""
fldigi_to_qrz.py

Intended to be run as an FLDigi <EXEC> macro. FLDigi exports the currently
selected logbook entry's fields as FLDIGI_LOGBOOK_* environment variables. This
script reads those, builds a single ADIF QSO record, and submits it to the QRZ
Logbook API (ACTION=INSERT).

Exit codes:
    0 - QSO uploaded successfully.
    1 - Aborted before upload (QRZ_KEY missing, or a required ADIF field
        is empty), or QRZ rejected the upload (RESULT != OK).
"""

import logging
import requests
import sys

from typing import Final
from urllib.parse import unquote_plus

import flenv
import utils

QRZ_API_URL: Final[str] = "https://logbook.qrz.com/api"

logger: logging.Logger = utils.get_fltools_logger()


def upload_to_qrz(api_key: str, adif_string: str) -> dict[str, str]:
    """
    Submit a single ADIF record to the QRZ Logbook API via ACTION=INSERT.

    Returns a dict with at least a "RESULT" key ("OK" or "FAIL").
    """

    # Form-encoded payload parameters required by the QRZ Logbook API.
    payload: dict[str, str | None] = {
        "KEY": api_key,
        "ACTION": "INSERT",
        "ADIF": adif_string,
        "OPTION": "REPLACE",
    }

    headers: dict[str, str] = {
        "User-Agent": utils.FLTOOLS_USER_AGENT,
    }

    try:
        # Send the POST request to QRZ.
        response: requests.Response = requests.post(
            QRZ_API_URL, data=payload, timeout=10, headers=headers
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"RESULT": "FAIL", "REASON": f"HTTP request failed: {e}"}

    return parse_qrz_response(response.text)


def parse_qrz_response(response_text: str) -> dict[str, str]:
    """
    Parse QRZ's plain-text "key=value&key=value" response body into a dict:
    e.g. "RESULT=OK&LOGID=12345&COUNT=1" -> {"RESULT": "OK", "LOGID":
    "12345", "COUNT": "1"}.
    """
    parsed: dict[str, str] = {}
    for pair in response_text.split("&"):
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        parsed[unquote_plus(key)] = unquote_plus(value)

    if "RESULT" not in parsed:
        return {
            "RESULT": "FAIL",
            "REASON": f"Unrecognized response from QRZ: {response_text!r}",
        }

    return parsed


def adif_fmt(key: str, value: str) -> str:
    """
    Format a single ADIF field as <fieldname:length>value.

    Returns an empty string for blank values, so that empty fields are
    simply omitted from the record rather than written out as <field:0>.
    """
    clean_value: str = value.strip()

    # ADIF TIME_ON / TIME_OFF fields must be digits only (HHMM or
    # HHMMSS), but FLDigi supplies them as "HH:MM:SS" -- strip the colons.
    if key in ["time_off", "time_on"]:
        clean_value = clean_value.replace(":", "")

    value_length: int = len(clean_value)
    if value_length > 0:
        return f"<{key}:{value_length}>{clean_value}"
    else:
        return ""


def to_adif(fields: dict[str, str]) -> str:
    """
    Build a single ADIF QSO record from a dict of ADIF field name -> value
    (as returned by get_field_values), terminated with <eor>.
    """
    adif_list = [adif_fmt(name, value) for name, value in fields.items()]
    return "".join(adif_list) + "<eor>"


def qrz() -> None:
    logger.info("Starting upload of new log entry.")

    # Load QRZ_KEY from a .env file next to this script
    qrz_key: str = flenv.get_env("QRZ_KEY")
    if not qrz_key:
        logger.error("QRZ_KEY is not set (check .env). Aborting upload.")
        sys.exit(1)

    flvars: dict[str, str] = flenv.get_env_all()
    fields: dict[str, str] = {
        adif_name: flvars[env_var] for env_var, adif_name in flenv.FLENV_KEY_MAP.items()
    }

    missing: list[str] = [
        name for name in flenv.QRZ_REQUIRED_ADIF_FIELDS if not fields.get(name)
    ]
    if missing:
        logger.error(
            f"Aborting upload: missing required field(s): {', '.join(missing)}"
        )
        sys.exit(1)

    adif_record: str = to_adif(fields)
    logger.debug(f"ADIF record: {adif_record}")

    result: dict[str, str] = upload_to_qrz(qrz_key, adif_record)

    if result.get("RESULT") == "OK":
        logger.info(f"QSO uploaded successfully (LOGID={result.get('LOGID', '?')}).")
    else:
        logger.error(f"QSO upload failed: {result}")
        sys.exit(1)
