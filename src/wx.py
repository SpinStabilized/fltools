"""
local_wx.py - Pull current conditions + active alerts from Pirate Weather
and print a compact, radio-friendly text block for use with FLDigi macros.
"""

import json
import logging
import maidenhead
import requests

from typing import Final

import flenv
import utils

logger: logging.Logger = utils.get_fltools_logger()

BASE_URL: Final[str] = "https://api.pirateweather.net/forecast"
TIMEOUT_SECONDS: Final[int] = 10
DEFAULT_LAT: Final[float] = 39.2037
DEFAULT_LON: Final[float] = -76.8610


def fetch_weather(api_key: str, lat: str, lon: str, units: str) -> dict:
    """Request only the 'currently' and 'alerts' blocks from Pirate Weather."""
    # Exclude everything except currently + alerts to keep the payload small
    # and the request fast (see Pirate Weather docs: exclude=).
    exclude = "minutely,hourly,daily,day_night,flags,summary"
    url = f"{BASE_URL}/{api_key}/{lat},{lon}" f"?units={units}&exclude={exclude}"

    headers = {"User-Agent": utils.FLTOOLS_USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        body = resp.text[:200] if resp is not None else ""  # type: ignore
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
    ix = int((deg / 22.5) + 0.5) % 16
    return dirs[ix]


def unit_labels(units: str = "") -> dict:
    """Return the display unit suffixes for the requested unit system. Defaults to SI units."""

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

    summary = cur.get("summary", "N/A")
    temp = cur.get("temperature")
    feels = cur.get("apparentTemperature")
    humidity = cur.get("humidity")
    wind_speed = cur.get("windSpeed")
    wind_bearing = cur.get("windBearing")
    pressure = cur.get("pressure")
    visibility = cur.get("visibility")
    uv = cur.get("uvIndex")

    parts = []
    parts.append(f"WX")
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


def wx():
    api_key: str = flenv.get_env("FLTOOLS_PW_API_KEY")
    units: str = flenv.get_env("FLTOOLS_PW_UNITS", "us")  # us, si, ca, uk, uk2
    my_grid: str = flenv.get_env("FLDIGI_MY_LOCATOR")

    if my_grid:
        latitude, longitude = maidenhead.to_location(my_grid, center=True)
    else:
        latitude, longitude = DEFAULT_LAT, DEFAULT_LON

    if not api_key or api_key == "":
        logger.error(
            "Pirate Weather API key not set. Edit pirate_wx.py or set PW_API_KEY."
        )

    try:
        data = fetch_weather(api_key, f"{latitude:0.4f}", f"{longitude:0.4f}", units)
    except RuntimeError as e:
        # Print something short so it doesn't break a macro insertion,
        # but also signal failure on stderr / exit code.
        logger.error("WX Unavailable.")
        logger.error(str(e))
        print("")

    output_lines = [format_current(data, units)]  # type: ignore

    alerts_text = format_alerts(data)  # type: ignore
    if alerts_text:
        output_lines.append("ALERTS: " + alerts_text)

    print("\n".join(output_lines))
