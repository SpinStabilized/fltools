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
    """Request only the 'currently' and 'alerts' blocks from Pirate Weather."""

    # Exclude everything except currently + alerts.
    exclude = "minutely,hourly,daily,day_night,flags,summary"
    url = f"{BASE_URL}/{api_key}/{lat},{lon}" f"?units={units}&exclude={exclude}"

    headers: dict[str, str] = {"User-Agent": identity.user_agent()}
    try:
        resp: requests.Response = requests.get(
            url, headers=headers, timeout=TIMEOUT_SECONDS
        )
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        body: str = resp.text[:200] if resp is not None else ""  # type: ignore
        logger.error(f"HTTP {resp.status_code} from Pirate Weather: {body}")  # type: ignore
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error reaching Pirate Weather: {e}")

    as_json: dict = {}
    try:
        as_json = resp.json()  # type: ignore
    except json.JSONDecodeError as e:
        logger.error(f"Could not parse Pirate Weather response: {e}")

    return as_json


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
    ix: int = int((deg / 22.5) + 0.5) % 16
    return dirs[ix]


def unit_labels(units: str = "") -> dict[str, str]:
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
    current: dict[str, Any] | None = data.get("currently")
    if not current:
        logger.error("Conditions returned empty.")
        return "Current conditions unavailable."

    wx_units = unit_labels(units)

    summary: str = current.get("summary", "N/A")
    temp: float = current.get("temperature")
    feels: float = current.get("apparentTemperature")
    humidity: float = current.get("humidity")
    wind_speed: float = current.get("windSpeed")
    wind_bearing: int = current.get("windBearing")
    visibility: float = current.get("visibility")

    parts: list[str] = []
    parts.append("WX")
    parts.append(f"{summary}")
    if temp is not None:
        line: str = f"Temp {temp:.0f}{wx_units['temp']}"
        if feels is not None and round(feels) != round(temp):
            line += f" (feels {feels:.0f}{wx_units['temp']})"
        parts.append(line)
    if humidity is not None:
        parts.append(f"Humidity {humidity * 100:.0f}%")
    if wind_speed is not None:
        wind_line: str = f"Wind {wind_speed:.0f}{wx_units['wind']}"
        if wind_bearing is not None:
            wind_line += f" {deg_to_compass(wind_bearing)}"
        parts.append(wind_line)
    if visibility is not None and visibility < 6.0:
        parts.append(f"Visibility {visibility:.0f}{wx_units['vis']}")
    conditions: str = " | ".join(parts)
    logger.info(conditions)
    return conditions


def format_alerts(data: dict) -> str:
    """Format the alert information to provide with the weather information."""
    alerts: list | None = data.get("alerts")
    alert_report: str = ""
    lines: list[str] = []

    if alerts:
        for a in alerts:
            title: str = a.get("title", "Alert")
            severity: str = a.get("severity", "Unknown")
            lines.append(f"[{severity.upper()}] {title}")
        lines = list(set(lines))
        alert_report: str = " | ".join(lines)

    return alert_report


def wx() -> None:
    api_key: str = flenv.get_env("FLTOOLS_PW_API_KEY")
    units: str = flenv.get_env("FLTOOLS_PW_UNITS", "us")  # us, si, ca, uk, uk2
    my_grid: str = flenv.get_env("FLDIGI_MY_LOCATOR")

    if my_grid:
        latitude, longitude = maidenhead.to_location(my_grid, center=True)
    else:
        latitude, longitude = DEFAULT_LAT, DEFAULT_LON

    if not api_key or api_key == "":
        logger.error(
            "Pirate Weather API key not set. Edit wx.py or set FLTOOLS_PW_API_KEY."
        )

    data: dict[str, Any] = {}
    try:
        data = fetch_weather(api_key, f"{latitude:0.4f}", f"{longitude:0.4f}", units)
        output_lines: list[str] = [format_current(data, units)]

        alerts_text: str = format_alerts(data)
        if alerts_text:
            output_lines.append(f"ALERTS: {alerts_text}")

        print("\n".join(output_lines))

    except RuntimeError as e:
        # Print something short so it doesn't break a macro insertion,
        # but also signal failure on stderr / exit code.
        logger.error("WX Unavailable.")
        logger.error(str(e))
        print("")
