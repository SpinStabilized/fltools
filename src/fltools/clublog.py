"""
clublog.py

Intended to be run as an FLDigi <EXEC> macro. FLDigi exports the currently
selected logbook entry's fields as FLDIGI_LOGBOOK_* environment variables. This
script reads those, builds a single ADIF QSO record, and submits it to the Club
Log real-time API (realtime.php).

Credentials are read from .env (run `fltools --paths` to see where that is):

    CLUBLOG_EMAIL=you@example.com
    CLUBLOG_PASSWORD=your-application-password
    CLUBLOG_API_KEY=your-api-key

Use an Application Password rather than your account password.

The callsign the QSO is filed under comes from FLDigi, not from .env, so that
the log reflects who was actually on the air. Club Log asks that each
callsign's QSOs stay in that callsign's log, and this installation holds one
account's credentials, so an upload is refused when the operator is not the
callsign fltools is configured for (FLTOOLS_CALL).

Lockout on authentication failure:

    FLDigi starts a fresh process for every <EXEC> call, so a single run has no
    way to stop the next one. If Club Log returns HTTP 403, this script writes
    a lockout file next to itself and every later run refuses to send anything
    until that file is removed. This matters: repeated failed credentials cause
    Club Log to firewall the originating IP address automatically.

    To resume after fixing the credentials, delete the lockout file.

Exit codes:
    0 - QSO accepted by Club Log (OK, modified, or already known / duplicate).
    1 - Aborted before upload (missing credentials, a required ADIF field, or
        the operator is not this installation's callsign), or Club Log
        rejected the QSO (HTTP 400).
    2 - Transient failure: network error or HTTP 500. Safe to retry later.
    3 - Authentication or form failure (HTTP 403), or a lockout left behind by
        an earlier 403. Do NOT retry until the credentials are corrected.
"""

import datetime
import logging
import sys
from typing import Final, NamedTuple

import requests

from fltools import flenv, identity, paths, utils

logger: logging.Logger = utils.get_fltools_logger()

# Club Log's real-time single-QSO endpoint. This is NOT for batches: uploading
# many QSOs back to back through it will get the IP address throttled or
# firewalled. Use putlogs.php for catch-up uploads of a whole ADIF file.
CLUBLOG_URL: Final[str] = "https://clublog.org/realtime.php"

# Exit codes (see module docstring)
EXIT_OK: Final[int] = 0
EXIT_FAIL: Final[int] = 1
EXIT_RETRY: Final[int] = 2
EXIT_AUTH: Final[int] = 3


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
        "CLUBLOG_CALLSIGN in .env, then delete this file to resume uploading.\n"
    )

    try:
        paths.LOCKOUT_FILE.write_text(note, encoding="utf-8")
    except OSError as e:
        logger.error(f"Could not write lockout file {paths.LOCKOUT_FILE}: {e}")
        return

    logger.error(
        f"Uploads disabled. Delete {paths.LOCKOUT_FILE} after fixing credentials."
    )


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
        "User-Agent": identity.user_agent(),
        "Content-Type": "application/x-www-form-urlencoded",
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

    match status:
        case 200:
            return UploadResult(True, EXIT_OK, message)
        case 400:
            return UploadResult(
                False, EXIT_FAIL, f"QSO rejected by Club Log: {message}"
            )
        case 403:
            return UploadResult(
                False,
                EXIT_AUTH,
                "Access denied by Club Log. Stop uploading and fix the "
                f"credentials before retrying, or this IP may be blocked: {message}",
            )
        case 500:
            return UploadResult(
                False,
                EXIT_RETRY,
                f"Club Log internal error, QSO not logged (retry later): {message}",
            )
        case _:
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
    if key in ["time_off", "time_on"]:
        clean_value = clean_value.replace(":", "")

    value_length: int = len(clean_value)
    if value_length > 0:
        return f"<{key}:{value_length}>{clean_value}"
    else:
        return ""


def to_adif(fields: dict[str, str]) -> str:
    """
    Build a single ADIF QSO record from a dict of ADIF field name -> value,
    terminated with <eor>.
    """
    adif_list = [adif_fmt(name, value) for name, value in fields.items()]
    return "".join(adif_list) + "<eor>"


def clublog() -> None:
    logger.info("Starting upload of new log entry.")

    # An earlier run was rejected by Club Log. Send nothing at all until a
    # human has fixed the credentials and removed the lockout, otherwise every
    # subsequent QSO adds another failed auth attempt against this IP address.
    if paths.LOCKOUT_FILE.exists():
        logger.error(
            f"Upload blocked: lockout in place at {paths.LOCKOUT_FILE}. Fix the "
            "Club Log credentials in .env, then delete that file."
        )
        sys.exit(EXIT_AUTH)

    # This installation holds one account's credentials, and Club Log wants
    # each callsign's QSOs in that callsign's own log. There is nothing useful
    # to do with someone else's contact from here.
    mismatch: tuple[str, str] | None = identity.operator_mismatch()
    if mismatch:
        station, configured = mismatch
        logger.error(
            f"Aborting upload: {station} is operating, but this installation "
            f"is configured for {configured}. The QSO would be filed in the "
            "wrong Club Log log."
        )
        sys.exit(EXIT_FAIL)

    email: str = flenv.get_env("CLUBLOG_EMAIL").strip()
    password: str = flenv.get_env("CLUBLOG_PASSWORD").strip()
    api_key: str = flenv.get_env("CLUBLOG_API_KEY").strip()

    # The callsign the QSO is filed under, from FLDigi. No configuration
    # override: the log has to reflect who was actually on the air.
    callsign: str = identity.station_callsign()

    credentials: dict[str, str] = {
        "CLUBLOG_EMAIL": email,
        "CLUBLOG_PASSWORD": password,
        "CLUBLOG_API_KEY": api_key,
        "FLDIGI_MY_CALL": callsign,
    }
    missing_creds: list[str] = [name for name, val in credentials.items() if not val]
    if missing_creds:
        logger.error(
            "Aborting upload: missing credential(s) in .env: "
            f"{', '.join(missing_creds)}"
        )
        sys.exit(EXIT_FAIL)

    fields: dict[str, str] = {
        adif_name: flenv.get_env(env_var).strip()
        for env_var, adif_name in flenv.FLENV_KEY_MAP.items()
    }

    # FLDigi does not export the station callsign as a logbook field, so it is
    # added here rather than left out of the record.
    fields["station_callsign"] = callsign

    missing: list[str] = [
        name for name in flenv.QRZ_REQUIRED_ADIF_FIELDS if not fields.get(name)
    ]
    if missing:
        logger.error(
            f"Aborting upload: missing required field(s): {', '.join(missing)}"
        )
        sys.exit(EXIT_FAIL)

    adif_record: str = to_adif(fields)
    logger.debug(f"ADIF record: {adif_record}")

    result: UploadResult = upload_to_clublog(
        email, password, api_key, callsign, adif_record
    )

    if result.accepted:
        logger.info(f"QSO with {fields['call']} accepted by Club Log: {result.message}")
    else:
        logger.error(f"QSO upload failed: {result.message}")
        if result.exit_code == EXIT_AUTH:
            engage_lockout(result.message)
        sys.exit(result.exit_code)
