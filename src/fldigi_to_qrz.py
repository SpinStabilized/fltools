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
import logging.handlers
import os
import pathlib
import sys

import requests

from dotenv import load_dotenv
from urllib.parse import unquote_plus

# Logging Parameters
LOG_FILE: str = "fldigi_to_qrz.log"
LOG_MAX_SIZE: int = 1_000_000
LOG_COUNT: int = 3
LOG_ENCODING: str = "utf-8"

# Anchor file paths to the script's own directory rather than the current
# working directory
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent

# Configure logging to a rotating file (caps log at ~1 MB, keeping up to 3
# old copies) so it doesn't grow too big over all QSOs being logged.
logging.basicConfig(
    handlers=[
        logging.handlers.RotatingFileHandler(
            SCRIPT_DIR / LOG_FILE, 
            maxBytes=LOG_MAX_SIZE, backupCount=LOG_COUNT, encoding=LOG_ENCODING
        )
    ],
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Maps the FLDigi macro environment variable names to the ADIF field names
# expected by the QRZ Logbook API.
key_map: dict[str, str] = {
    'FLDIGI_LOGBOOK_ARRL_SECT_IN': 'arrl_sect',
    'FLDIGI_LOGBOOK_BAND': 'band',
    'FLDIGI_LOGBOOK_CALL': 'call',
    'FLDIGI_LOGBOOK_CLASS_IN': 'class',
    'FLDIGI_LOGBOOK_CONTINENT': 'cont',
    'FLDIGI_LOGBOOK_COUNTRY': 'country',
    'FLDIGI_LOGBOOK_COUNTY': 'cnty',
    'FLDIGI_LOGBOOK_CQZ': 'cqz',
    'FLDIGI_LOGBOOK_DATE_OFF': 'qso_date_off',
    'FLDIGI_LOGBOOK_DATE': 'qso_date',
    'FLDIGI_LOGBOOK_DXCC': 'dxcc',
    'FLDIGI_LOGBOOK_FREQUENCY': 'freq',
    'FLDIGI_LOGBOOK_IOTA': 'iota',
    'FLDIGI_LOGBOOK_ITUZ': 'ituz',
    'FLDIGI_LOGBOOK_LOCATOR': 'gridsquare',
    'FLDIGI_LOGBOOK_MODE': 'mode',
    'FLDIGI_LOGBOOK_NAME': 'name',
    'FLDIGI_LOGBOOK_NOTES': 'notes',
    'FLDIGI_LOGBOOK_QSL_VIA': 'qsl_via',
    'FLDIGI_LOGBOOK_QTH': 'qth',
    'FLDIGI_LOGBOOK_RST_IN': 'rst_rcvd',
    'FLDIGI_LOGBOOK_RST_OUT': 'rst_sent',
    'FLDIGI_LOGBOOK_SERNO_IN': 'srx',
    'FLDIGI_LOGBOOK_SERNO_OUT': 'stx',
    'FLDIGI_LOGBOOK_STATE': 'state',
    'FLDIGI_LOGBOOK_TIME_OFF': 'time_off',
    'FLDIGI_LOGBOOK_TIME_ON': 'time_on',
    'FLDIGI_LOGBOOK_TX_PWR': 'tx_pwr',
    'FLDIGI_LOGBOOK_VE_PROV': 've_prov',
}

# ADIF fields QRZ's logbook API needs at minimum to accept a QSO record.
REQUIRED_ADIF_FIELDS: list[str] = [
    'call', 'qso_date', 'time_on', 'band', 'mode',
    ]


def upload_to_qrz(api_key: str, adif_string: str) -> dict[str, str]:
    """
    Submit a single ADIF record to the QRZ Logbook API via ACTION=INSERT.

    Returns a dict with at least a "RESULT" key ("OK" or "FAIL").
    """
    url: str = "https://logbook.qrz.com/api"

    # Form-encoded payload parameters required by the QRZ Logbook API.
    payload: dict[str, str | None] = {
        "KEY": api_key,
        "ACTION": "INSERT",
        "ADIF": adif_string,
        "OPTION": "REPLACE"
    }

    headers: dict[str, str] = {
        'User-Agent': 'fldigi_to_qrz/0.1.0 (N3BMC)',
    }

    try:
        # Send the POST request to QRZ.
        response: requests.Response = requests.post(
            url, data=payload, timeout=10, headers=headers
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
            "REASON": f"Unrecognized response from QRZ: {response_text!r}",}

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
    if key in ['time_off', 'time_on']:
        clean_value = clean_value.replace(":", "")

    value_length: int = len(clean_value)
    if value_length > 0:
        return f'<{key}:{value_length}>{clean_value}'
    else:
        return ''


def to_adif(fields: dict[str, str]) -> str:
    """
    Build a single ADIF QSO record from a dict of ADIF field name -> value
    (as returned by get_field_values), terminated with <eor>.
    """
    adif_list = [adif_fmt(name, value) for name, value in fields.items()]
    return ''.join(adif_list) + '<eor>'


def main() -> None:
    logging.info('Starting upload of new log entry.')

    # Load QRZ_KEY from a .env file next to this script
    load_dotenv(SCRIPT_DIR / '.env')
    qrz_key: str = os.getenv("QRZ_KEY", "")
    if not qrz_key:
        logging.error("QRZ_KEY is not set (check .env). Aborting upload.")
        sys.exit(1)

    fields: dict[str, str] = {
        adif_name: os.getenv(env_var, "").strip()
        for env_var, adif_name in key_map.items()
    }

    missing: list[str] = [name for name in REQUIRED_ADIF_FIELDS if not fields.get(name)]
    if missing:
        logging.error(f"Aborting upload: missing required field(s): {', '.join(missing)}")
        sys.exit(1)

    adif_record: str = to_adif(fields)
    logging.debug(f"ADIF record: {adif_record}")

    result: dict[str, str] = upload_to_qrz(qrz_key, adif_record)

    if result.get("RESULT") == "OK":
        logging.info(f"QSO uploaded successfully (LOGID={result.get('LOGID', '?')}).")
    else:
        logging.error(f"QSO upload failed: {result}")
        sys.exit(1)


if __name__ == "__main__":
    main()