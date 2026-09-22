"""
wx.py - Pull current conditions + active alerts from Pirate Weather
and print a compact, radio-friendly text block for use with FLDigi macros.
"""

import json
import logging
from typing import Any, Final

import maidenhead
import requests

from fltools import flenv, identity, utils

logger: logging.Logger = utils.get_fltools_logger()

BASE_URL: Final[str] = "https://api.pirateweather.net/forecast"
TIMEOUT_SECONDS: Final[int] = 10
DEFAULT_LAT: Final[float] = 39.2037
DEFAULT_LON: Final[float] = -76.8610


def fetch_weather(api_key: str, lat: str, lon: str, units: str) -> dict[str, Any]:
    """
    Request only the 'currently' and 'alerts' blocks from Pirate Weather.

    Returns an empty dict on any failure, so the caller can treat "no weather
    available" as a normal outcome rather than transmitting a half-built line.
    """
    # Exclude everything except currently + alerts to keep the payload small
    # and the request fast (see Pirate Weather docs: exclude=).
    exclude = "minutely,hourly,daily,day_night,flags,summary"
    url = f"{BASE_URL}/{api_key}/{lat},{lon}" f"?units={units}&exclude={exclude}"

    headers: dict[str, str] = {"User-Agent": identity.user_agent()}
    try:
        resp: requests.Response = requests.get(
            url, headers=headers, timeout=TIMEOUT_SECONDS
        )
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        # Reached through the exception rather than through resp: a failure
        # inside requests.get() leaves resp unbound entirely, and referring to
        # it here is exactly what the old "type: ignore" comments were hiding.
        if e.response is not None:
            detail: str = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
        else:
            detail = str(e)
        logger.error(f"Pirate Weather refused the request: {detail}")
        return {}
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error reaching Pirate Weather: {e}")
        return {}

    try:
        # Bound to a name rather than returned directly: resp.json() is typed
        # Any, which warn_return_any flags.
        payload: dict[str, Any] = resp.json()
    except json.JSONDecodeError as e:
        logger.error(f"Could not parse Pirate Weather response: {e}")
        return {}

    return payload


def deg_to_compass(deg: int) -> str:
    """Convert a wind bearing in degrees to a 16-point compass direction."""
    if deg is None:
        return "N/A"
    dirs = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]
    ix = int((deg / 22.5) + 0.5) % 16
    return dirs[ix]


def unit_labels(units: str = "") -> dict:
    """Return display unit suffixes for the requested unit system. Defaults to SI."""

    units_dict: dict[str, str] = {
        "temp": "C",
        "wind": "m/s",
        "vis": "km",
        "press": "hPa",
    }
    match units:
        case "us":
            units_dict = {"temp": "F", "wind": "mph", "vis": "mi", "press": "mb"}
        case "uk" | "uk2":
            units_dict = {"temp": "C", "wind": "mph", "vis": "mi", "press": "hPa"}
        case "ca":
            units_dict = {"temp": "C", "wind": "km/h", "vis": "km", "press": "hPa"}

    return units_dict


def format_current(data: dict, units: str) -> str:
    """Format the current conditions for human ingestion."""
    cur = data.get("currently")
    if not cur:
        return "Current conditions unavailable."

    u = unit_labels(units)

    summary: str = cur.get("summary", "N/A")
    temp: float = cur.get("temperature")
    feels: float = cur.get("apparentTemperature")
    humidity: float = cur.get("humidity")
    wind_speed: float = cur.get("windSpeed")
    wind_bearing: int = cur.get("windBearing")
    # visibility = cur.get("visibility")

    parts = []
    parts.append("WX")
    parts.append(f"{summary}")
    if temp is not None:
        line = f"Temp {temp:.0f}{u['temp']}"
        if feels is not None and round(feels) != round(temp):
            line += f" (feels {feels:.0f}{u['temp']})"
        parts.append(line)
    if humidity is not None:
        parts.append(f"Humidity {humidity * 100:.0f}%")
    if wind_speed is not None:
        wind_line = f"Wind {wind_speed:.0f}{u['wind']}"
        if wind_bearing is not None:
            wind_line += f" {deg_to_compass(wind_bearing)}"
        parts.append(wind_line)

    return " | ".join(parts)


def format_alerts(data: dict) -> str:
    """Format the alert information to provide with the weather information."""
    alerts: list | None = data.get("alerts")
    alert_report: str = ""
    lines = []

    if alerts:
        for a in alerts:
            title = a.get("title", "Alert")
            severity = a.get("severity", "Unknown")
            lines.append(f"[{severity.upper()}] {title}")
        lines = list(set(lines))
        alert_report = " | ".join(lines)

    return alert_report


def wx() -> None:
    """
    Print current conditions and any active alerts for the station's grid.

    Prints nothing at all when the weather cannot be fetched. This output goes
    straight into FLDigi's transmit buffer, so a partial or empty line is worse
    than no line: it would be sent over the air. Failures are reported in the
    log instead.
    """
    api_key: str = flenv.get_env("FLTOOLS_PW_API_KEY")
    units: str = flenv.get_env("FLTOOLS_PW_UNITS", "us")  # us, si, ca, uk, uk2
    my_grid: str = flenv.get_env("FLDIGI_MY_LOCATOR").strip()

    if not api_key:
        logger.error("FLTOOLS_PW_API_KEY is not set (check .env). No weather sent.")
        return

    latitude: float
    longitude: float
    if my_grid:
        latitude, longitude = maidenhead.to_location(my_grid, center=True)
    else:
        logger.warning(
            "FLDIGI_MY_LOCATOR is empty, falling back to the default location. "
            "Set your grid square in FLDigi under Configure > Operator > Station."
        )
        latitude, longitude = DEFAULT_LAT, DEFAULT_LON

    logger.info(
        f"Weather for {my_grid or 'default location'} "
        f"({latitude:0.4f}, {longitude:0.4f})"
    )

    data: dict[str, Any] = fetch_weather(
        api_key, f"{latitude:0.4f}", f"{longitude:0.4f}", units
    )
    if not data:
        # fetch_weather has already logged why. Say nothing on stdout.
        logger.error("No weather data available, nothing sent to the transmit buffer.")
        return

    output_lines: list[str] = [format_current(data, units)]

    alerts_text: str = format_alerts(data)
    if alerts_text:
        output_lines.append("ALERTS: " + alerts_text)

    print("\n".join(output_lines))
