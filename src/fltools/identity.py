"""
Who fltools is, and who is on the air.

These are two different things and they deliberately do not share a source.

    station_callsign()     the call the QSO happened under. FLDigi owns this,
                           always. Whoever sits down at the radio and sets
                           their call in FLDigi is who gets logged.

    configured_callsign()  the call this installation is set up for, from
                           FLTOOLS_CALL. The QRZ key and Club Log account in
                           .env belong to this callsign. It also identifies
                           the software to upstream APIs.

Normally these are the same and nothing interesting happens. When they differ,
someone else is operating, and that matters: fltools holds one set of
credentials, QRZ's API key selects the destination logbook with no callsign
parameter to redirect it, and Club Log asks that each callsign's QSOs stay in
that callsign's log. An upload in that state files a QSO in the wrong place,
so callers check first and refuse.

Neither value falls back to the other. Falling back would defeat both the
guard and the point of a stable software identity.

Values are resolved on demand rather than bound as module constants.
FLTOOLS_CALL comes from .env, which cli.main() does not load until after
every module has been imported, so a constant built at import time would
capture an empty string.

os.getenv is used directly rather than flenv.get_env because flenv imports
utils for its logger, and routing through it would close an import cycle.
The two are equivalent: flenv.get_env is a thin wrapper.
"""

import os
from typing import Final

from fltools import __version__

APP_NAME: Final[str] = "fltools"


def station_callsign() -> str:
    """
    The callsign the QSO was made under, from FLDigi and nowhere else.

    This is what belongs in a log record. There is no configuration override
    on purpose: the log has to reflect who was actually on the air, and the
    only thing that knows that is the station FLDigi is set up as right now.

    Returns an empty string when FLDigi did not export it, which happens
    outside an <EXEC> macro.
    """
    return os.getenv("FLDIGI_MY_CALL", "").strip().upper()


def configured_callsign() -> str:
    """
    The callsign this installation is configured for, from FLTOOLS_CALL.

    The credentials in .env belong to this callsign's logbooks and accounts.
    It is a property of the install rather than of whoever is operating, so
    it stays put when the operator changes.

    Returns an empty string when unset.
    """
    return os.getenv("FLTOOLS_CALL", "").strip().upper()


def operator_mismatch() -> tuple[str, str] | None:
    """
    Report a station/configuration callsign mismatch, or None when fine.

    Returns (station, configured) when the operator is not the callsign this
    installation holds credentials for. Callers decide what to do about it;
    the upload paths abort, because there is no way to route a QSO to the
    right logbook from here.

    Returns None when the two agree, and also when either is unset: a missing
    value is a separate problem with its own error message, and reporting it
    as a mismatch would be misleading.

    Note that portable and mobile identifiers make a different callsign for
    this purpose. N3BMC/P is not N3BMC: QRZ keeps a separate logbook for it,
    and Club Log expects it registered separately on the account.
    """
    station: str = station_callsign()
    configured: str = configured_callsign()

    if not station or not configured:
        return None
    if station == configured:
        return None
    return (station, configured)


def user_agent() -> str:
    """
    Identify fltools to the upstream APIs.

    QRZ requires an identifiable user agent and asks that personal scripts
    include the operator's callsign and a script name. Club Log logs it too,
    and a real callsign in there makes a support request far easier to
    answer. The callsign is omitted rather than left as empty parentheses
    when FLTOOLS_CALL is unset.
    """
    callsign: str = configured_callsign()
    if callsign:
        return f"{APP_NAME}/{__version__} ({callsign})"
    return f"{APP_NAME}/{__version__}"
