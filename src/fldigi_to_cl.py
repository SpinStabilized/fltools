"""
fldigi_to_clublog.py

Intended to be run as an FLDigi <EXEC> macro. FLDigi exports the currently
selected logbook entry's fields as FLDIGI_LOGBOOK_* environment variables. This
script reads those, builds a single ADIF QSO record, and submits it to the Club
Log real-time API (realtime.php).

Credentials are read from a .env file next to this script:

    CLUBLOG_EMAIL=you@example.com
    CLUBLOG_PASSWORD=your-application-password
    CLUBLOG_API_KEY=your-api-key
    CLUBLOG_CALLSIGN=KB3BMC

CLUBLOG_CALLSIGN is optional; if omitted the script falls back to FLDigi's
FLDIGI_MY_CALL environment variable. Use an Application Password rather than
your account password.

Lockout on authentication failure:

    FLDigi starts a fresh process for every <EXEC> call, so a single run has no
    way to stop the next one. If Club Log returns HTTP 403, this script writes
    a lockout file next to itself and every later run refuses to send anything
    until that file is removed. This matters: repeated failed credentials cause
    Club Log to firewall the originating IP address automatically.

    To resume after fixing the credentials, either delete the lockout file or
    run this script with --clear-lockout.

Exit codes:
    0 - QSO accepted by Club Log (OK, modified, or already known / duplicate).
    1 - Aborted before upload (missing credentials or a required ADIF field),
        or Club Log rejected the QSO (HTTP 400).
    2 - Transient failure: network error or HTTP 500. Safe to retry later.
    3 - Authentication or form failure (HTTP 403), or a lockout left behind by
        an earlier 403. Do NOT retry until the credentials are corrected.
"""

import datetime
import logging
import logging.handlers
import os
import pathlib
import sys

from typing import NamedTuple

import requests

from dotenv import load_dotenv

# Logging Parameters
LOG_FILE: str = "fldigi_to_clublog.log"
LOG_MAX_SIZE: int = 1_000_000
LOG_COUNT: int = 3
LOG_ENCODING: str = "utf-8"

# Written beside this script when Club Log returns 403, and checked at the
# start of every run. Its presence blocks all further uploads.
LOCKOUT_FILE: str = "clublog_lockout.txt"

# Club Log's real-time single-QSO endpoint. This is NOT for batches: uploading
# many QSOs back to back through it will get the IP address throttled or
# firewalled. Use putlogs.php for catch-up uploads of a whole ADIF file.
CLUBLOG_URL: str = "https://clublog.org/realtime.php"

# Exit codes (see module docstring)
EXIT_OK: int = 0
EXIT_FAIL: int = 1
EXIT_RETRY: int = 2
EXIT_AUTH: int = 3

# Anchor file paths to the script's own directory rather than the current
# working directory. FLDigi invokes <EXEC> macros with an unpredictable cwd,
# and resolve() follows any symlink to the real location of this file, so the
# log and the lockout live beside the source no matter how it was launched.
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
LOCKOUT_PATH = SCRIPT_DIR / LOCKOUT_FILE

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
# Club Log's ADIF parser understands.
key_map: dict[str, str] = {
    'FLDIGI_LOGBOOK_BAND': 'band',
    'FLDIGI_LOGBOOK_CALL': 'call',
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

# ADIF fields needed at minimum for Club Log to place the QSO correctly.
REQUIRED_ADIF_FIELDS: list[str] = [
    'call', 'qso_date', 'time_on', 'band', 'mode',
    ]


class UploadResult(NamedTuple):
    """Outcome of a single real-time upload attempt."""
    accepted: bool
    exit_code: int
    message: str


def engage_lockout(reason: str) -> None:
    """
    Record a credentials failure so that later runs refuse to upload.

    A failure to write the lockout is logged but not raised: the upload has
    already failed and the caller is on its way to exiting anyway.
    """
    stamp: str = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    note: str = (
        "Club Log uploads are disabled because the credentials were rejected.\n"
        f"Time: {stamp}\n"
        f"Club Log said: {reason}\n\n"
        "Fix CLUBLOG_EMAIL, CLUBLOG_PASSWORD, CLUBLOG_API_KEY or "
        "CLUBLOG_CALLSIGN in .env, then delete this file (or run the script\n"
        "with --clear-lockout) to resume uploading.\n"
    )

    try:
        LOCKOUT_PATH.write_text(note, encoding="utf-8")
    except OSError as e:
        logging.error(f"Could not write lockout file {LOCKOUT_PATH}: {e}")
        return

    logging.error(
        f"Uploads disabled. Delete {LOCKOUT_PATH} after fixing credentials."
    )


def clear_lockout() -> int:
    """
    Remove the lockout file, if present. Returns a process exit code.
    """
    try:
        LOCKOUT_PATH.unlink()
    except FileNotFoundError:
        logging.info(f"No lockout in place at {LOCKOUT_PATH}; nothing to clear.")
        return EXIT_OK
    except OSError as e:
        logging.error(f"Could not remove lockout file {LOCKOUT_PATH}: {e}")
        return EXIT_FAIL

    logging.info(f"Lockout cleared ({LOCKOUT_PATH}). Uploads re-enabled.")
    return EXIT_OK


def upload_to_clublog(
    email: str, password: str, api_key: str, callsign: str, adif_string: str
) -> UploadResult:
    """
    Submit a single ADIF record to the Club Log real-time API.

    Club Log signals the outcome through the HTTP status code, with a
    human-readable explanation in the response body, rather than through a
    structured payload.
    """
    # Form-encoded payload parameters required by realtime.php.
    payload: dict[str, str] = {
        "email": email,
        "password": password,
        "callsign": callsign,
        "adif": adif_string,
        "api": api_key,
    }

    headers: dict[str, str] = {
        'User-Agent': 'fldigi_to_clublog/0.1.0 (KB3BMC)',
        'Content-Type': 'application/x-www-form-urlencoded',
    }

    try:
        # Send the POST request to Club Log. requests url-encodes the form
        # values for us, so callsigns with slashes and notes with spaces or
        # ampersands come through intact.
        response: requests.Response = requests.post(
            CLUBLOG_URL, data=payload, timeout=10, headers=headers
            )
    except requests.exceptions.RequestException as e:
        return UploadResult(False, EXIT_RETRY, f"HTTP request failed: {e}")

    return interpret_clublog_response(response.status_code, response.text)


def interpret_clublog_response(status: int, body: str) -> UploadResult:
    """
    Turn a Club Log HTTP status code and response body into an UploadResult.

    200 covers three cases (stored, modified, or already known); all three
    count as success. 400 means the QSO itself was rejected, 403 means the
    credentials or form were bad, and 500 means Club Log had a problem on its
    end.
    """
    message: str = body.strip() or "(no message body)"

    if status == 200:
        return UploadResult(True, EXIT_OK, message)

    if status == 400:
        return UploadResult(False, EXIT_FAIL, f"QSO rejected by Club Log: {message}")

    if status == 403:
        return UploadResult(
            False, EXIT_AUTH,
            "Access denied by Club Log. Stop uploading and fix the "
            f"credentials before retrying, or this IP may be blocked: {message}"
        )

    if status == 500:
        return UploadResult(
            False, EXIT_RETRY,
            f"Club Log internal error, QSO not logged (retry later): {message}"
        )

    return UploadResult(
        False, EXIT_FAIL, f"Unexpected HTTP {status} from Club Log: {message}"
    )


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
    Build a single ADIF QSO record from a dict of ADIF field name -> value,
    terminated with <eor>.
    """
    adif_list = [adif_fmt(name, value) for name, value in fields.items()]
    return ''.join(adif_list) + '<eor>'


def main() -> None:
    if "--clear-lockout" in sys.argv[1:]:
        sys.exit(clear_lockout())

    logging.info('Starting upload of new log entry.')

    # An earlier run was rejected by Club Log. Send nothing at all until a
    # human has fixed the credentials and removed the lockout, otherwise every
    # subsequent QSO adds another failed auth attempt against this IP address.
    if LOCKOUT_PATH.exists():
        logging.error(
            f"Upload blocked: lockout in place at {LOCKOUT_PATH}. Fix the "
            "Club Log credentials in .env, then delete that file (or run this "
            "script with --clear-lockout)."
        )
        sys.exit(EXIT_AUTH)

    # Load Club Log credentials from a .env file next to this script
    load_dotenv(SCRIPT_DIR / '.env')
    email: str = os.getenv("CLUBLOG_EMAIL", "").strip()
    password: str = os.getenv("CLUBLOG_PASSWORD", "").strip()
    api_key: str = os.getenv("CLUBLOG_API_KEY", "").strip()

    # The station callsign the QSO is logged under. Fall back to the callsign
    # FLDigi is configured with if .env doesn't pin one down.
    callsign: str = (
        os.getenv("CLUBLOG_CALLSIGN", "").strip()
        or os.getenv("FLDIGI_MY_CALL", "").strip()
    )

    credentials: dict[str, str] = {
        "CLUBLOG_EMAIL": email,
        "CLUBLOG_PASSWORD": password,
        "CLUBLOG_API_KEY": api_key,
        "CLUBLOG_CALLSIGN": callsign,
    }
    missing_creds: list[str] = [name for name, val in credentials.items() if not val]
    if missing_creds:
        logging.error(
            "Aborting upload: missing credential(s) in .env: "
            f"{', '.join(missing_creds)}"
        )
        sys.exit(EXIT_FAIL)

    fields: dict[str, str] = {
        adif_name: os.getenv(env_var, "").strip()
        for env_var, adif_name in key_map.items()
    }

    missing: list[str] = [name for name in REQUIRED_ADIF_FIELDS if not fields.get(name)]
    if missing:
        logging.error(f"Aborting upload: missing required field(s): {', '.join(missing)}")
        sys.exit(EXIT_FAIL)

    adif_record: str = to_adif(fields)
    logging.debug(f"ADIF record: {adif_record}")

    result: UploadResult = upload_to_clublog(
        email, password, api_key, callsign, adif_record
    )

    if result.accepted:
        logging.info(
            f"QSO with {fields['call']} accepted by Club Log: {result.message}"
        )
        sys.exit(EXIT_OK)

    logging.error(f"QSO upload failed: {result.message}")

    if result.exit_code == EXIT_AUTH:
        engage_lockout(result.message)

    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()