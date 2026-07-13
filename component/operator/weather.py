"""Open-Meteo weather API client.

Open-Meteo is a free, open-source weather API that requires no API key.
Rate limit: 10,000 calls/day (non-commercial).
Docs: https://open-meteo.com/en/docs
"""

from __future__ import annotations

from typing import Any

import httpx

_BASE = "https://api.open-meteo.com/v1"
_ARCHIVE_BASE = "https://archive-api.open-meteo.com/v1"
_TIMEOUT = 15.0

# Open-Meteo defaults to metric (°C, km/h, mm). Request US units on every call so
# a 34°C reading can't be misread as 34°F. temperature/windspeed apply to every
# endpoint; the daily queries additionally request inches of precipitation.
_US_UNITS = {"temperature_unit": "fahrenheit", "windspeed_unit": "mph"}
_DAILY_FIELDS = "temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode"


async def _get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET ``url`` with ``params``, returning parsed JSON and raising on non-2xx."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


async def get_current(lat: float, lon: float) -> dict[str, Any]:
    """Fetch current weather conditions for a latitude/longitude.

    Returns temperature, wind speed, wind direction, and weather code.
    """
    data = await _get(
        f"{_BASE}/forecast",
        {"latitude": lat, "longitude": lon, "current_weather": "true", **_US_UNITS},
    )
    return {
        "success": True,
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "current_weather": data.get("current_weather"),
        "current_weather_units": {"temperature": "°F", "windspeed": "mph", "winddirection": "°"},
        "timezone": data.get("timezone"),
    }


async def get_forecast(lat: float, lon: float, days: int = 7) -> dict[str, Any]:
    """Fetch a multi-day weather forecast (1-16 days).

    Returns daily high/low temperatures, precipitation, and weather codes.
    """
    days = max(1, min(days, 16))
    data = await _get(
        f"{_BASE}/forecast",
        {
            "latitude": lat,
            "longitude": lon,
            "daily": _DAILY_FIELDS,
            "precipitation_unit": "inch",
            "forecast_days": days,
            "timezone": "auto",
            **_US_UNITS,
        },
    )
    return {
        "success": True,
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "forecast_days": days,
        "daily": data.get("daily"),
        "daily_units": data.get("daily_units"),
        "timezone": data.get("timezone"),
    }


async def get_historical(lat: float, lon: float, start: str, end: str) -> dict[str, Any]:
    """Fetch historical weather data for a date range.

    Args:
        lat: Latitude (-90 to 90).
        lon: Longitude (-180 to 180).
        start: Start date (YYYY-MM-DD).
        end: End date (YYYY-MM-DD).

    Returns daily temperature, precipitation, and weather codes.
    """
    data = await _get(
        f"{_ARCHIVE_BASE}/archive",
        {
            "latitude": lat,
            "longitude": lon,
            "start_date": start,
            "end_date": end,
            "daily": _DAILY_FIELDS,
            "precipitation_unit": "inch",
            "timezone": "auto",
            **_US_UNITS,
        },
    )
    return {
        "success": True,
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "start_date": start,
        "end_date": end,
        "daily": data.get("daily"),
        "daily_units": data.get("daily_units"),
        "timezone": data.get("timezone"),
    }
