"""
Resolution of the on-disk locations fltools reads and writes.

Anchoring to __file__ stopped being meaningful once fltools became an
installable package. After `uv tool install` the code lives inside a
uv-managed virtual environment, and nothing the operator edits by hand lives
beside it. These locations follow platform convention instead, with one
environment variable as an escape hatch.

Set FLTOOLS_HOME to pin every location under a single directory. This is the
simplest way to run against a scratch configuration while developing, and an
option for anyone who would rather keep all of fltools' files in one place
than follow platform convention.

    FLTOOLS_HOME=~/.fltools
        .env
        logs/fltools.log
        state/clublog_lockout.txt

Do not point FLTOOLS_HOME inside ~/.fldigi. Deleting that directory is a
routine FLDigi troubleshooting step, and re-keying QRZ and Club Log
credentials afterward is a poor reward for fixing a waterfall problem.

Set FLTOOLS_ENV to point at one specific .env file, overriding only the
config location. This is the supported replacement for editing the load
path in the source.
"""

import os
import pathlib
from typing import Final

import platformdirs

APP_NAME: Final[str] = "fltools"

# appauthor=False keeps Windows from inserting a publisher directory above
# the application directory.
_DIRS: Final[platformdirs.PlatformDirs] = platformdirs.PlatformDirs(
    appname=APP_NAME, appauthor=False
)

_HOME_OVERRIDE: Final[str] = os.getenv("FLTOOLS_HOME", "").strip()
_ENV_OVERRIDE: Final[str] = os.getenv("FLTOOLS_ENV", "").strip()


def _home() -> pathlib.Path | None:
    """The FLTOOLS_HOME directory, or None when it is not set."""
    if not _HOME_OVERRIDE:
        return None
    return pathlib.Path(_HOME_OVERRIDE).expanduser().resolve()


# Where the operator's .env lives.
CONFIG_DIR: Final[pathlib.Path] = _home() or pathlib.Path(_DIRS.user_config_dir)

# Where the rotating log is written.
LOG_DIR: Final[pathlib.Path] = (
    (_home() / "logs") if _home() else pathlib.Path(_DIRS.user_log_dir)  # type: ignore
)

# Where fltools keeps its own bookkeeping, such as the Club Log lockout.
STATE_DIR: Final[pathlib.Path] = (
    (_home() / "state") if _home() else pathlib.Path(_DIRS.user_state_dir)  # type: ignore
)

ENV_FILE: Final[pathlib.Path] = (
    pathlib.Path(_ENV_OVERRIDE).expanduser().resolve()
    if _ENV_OVERRIDE
    else CONFIG_DIR / ".env"
)

LOG_FILE: Final[pathlib.Path] = LOG_DIR / f"{APP_NAME}.log"

LOCKOUT_FILE: Final[pathlib.Path] = STATE_DIR / "clublog_lockout.txt"


def ensure_dirs() -> None:
    """
    Create the directories fltools writes into.

    CONFIG_DIR is created as well, even though fltools never writes there, so
    that a first run leaves the operator an obvious place to drop .env.
    """
    for directory in (CONFIG_DIR, LOG_DIR, STATE_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def fldigi_config_dir() -> pathlib.Path | None:
    """
    The configuration directory of the FLDigi instance that invoked us.

    FLDigi exports FLDIGI_CONFIG_DIR to its <EXEC> children, which is the only
    way to tell one instance from another: a station running several rigs
    launches an instance per configuration (fldigi --config-dir DIRECTORY),
    and they all share one fltools log.

    Not a location fltools reads or writes, and unset outside a macro. Returns
    None rather than a default, because guessing which instance called would
    be worse than admitting we do not know.
    """
    value: str = os.getenv("FLDIGI_CONFIG_DIR", "").strip()
    return pathlib.Path(value) if value else None


def describe() -> dict[str, pathlib.Path]:
    """
    Every resolved location, for the `fltools --paths` flag.

    The FLDigi configuration directory is included only when FLDigi set it,
    since outside an <EXEC> macro there is nothing to report.
    """
    described: dict[str, pathlib.Path] = {
        "config dir": CONFIG_DIR,
        "env file": ENV_FILE,
        "log dir": LOG_DIR,
        "log file": LOG_FILE,
        "state dir": STATE_DIR,
        "lockout file": LOCKOUT_FILE,
    }

    calling_instance: pathlib.Path | None = fldigi_config_dir()
    if calling_instance is not None:
        described["fldigi config dir"] = calling_instance

    return described
