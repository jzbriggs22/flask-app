"""LocalWeatherGPT: analytics and forecasting toolkit for agricultural planning.

This module fetches daily weather data from Meteostat, Open-Meteo, NOAA, and
Visual Crossing; aggregates statistics; produces visualizations; and surfaces
near-term forecast guidance tailored to farm operations.
"""
from __future__ import annotations

import argparse
import getpass
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Dict, Iterable, Optional

import matplotlib

# Use non-interactive backend so scripts run on servers
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from dateutil import parser
import requests
from geopy.exc import GeopyError
from geopy.geocoders import Nominatim
from meteostat import Daily, Point
from pandas.tseries.offsets import MonthEnd


logging.basicConfig(level=logging.INFO)


DATA_SOURCES = {
    "Meteostat": "https://meteostat.net/",
    "Open-Meteo": "https://open-meteo.com/",
    "NOAA CDO": "https://www.ncei.noaa.gov/cdo-web/",
    "Visual Crossing": "https://www.visualcrossing.com/",
}
DEFAULT_LOCATION = "Buchanan, MI"
DEFAULT_BASE_TEMP_F = 50.0
DEFAULT_FORECAST_DAYS = 7
GEOCODER_USER_AGENT = os.getenv("GEOCODER_USER_AGENT", "localweathergpt")
VISUAL_CROSSING_API_KEY = os.getenv("VISUAL_CROSSING_API_KEY")
NOAA_TOKEN = os.getenv("NOAA_TOKEN")
NOAA_STATION_ID = os.getenv("NOAA_STATION_ID")

MPS_TO_MPH = 2.23693629
STANDARD_COLUMNS = [
    "Date",
    "Source",
    "High_F",
    "Low_F",
    "Avg_F",
    "Rain_in",
    "Snow_in",
    "Humidity_pct",
    "WindSpeed_mph",
]

VISUAL_CROSSING_OPTIONAL_FIELDS = {
    "degreedays": "DegreeDays",
    "accdegreedays": "AccumDegreeDays",
    "soiltemp01": "SoilTemp_0_1m_F",
    "soiltemp04": "SoilTemp_0_4m_F",
    "soiltemp10": "SoilTemp_1_0m_F",
    "soiltemp20": "SoilTemp_2_0m_F",
    "soilmoisture01": "SoilMoisture_0_1m_pc",
    "soilmoisture04": "SoilMoisture_0_4m_pc",
    "soilmoisture10": "SoilMoisture_1_0m_pc",
    "soilmoisture20": "SoilMoisture_2_0m_pc",
    "soilmoisturevol01": "SoilMoistureVol_0_1m",
    "soilmoisturevol04": "SoilMoistureVol_0_4m",
    "soilmoisturevol10": "SoilMoistureVol_1_0m",
    "soilmoisturevol20": "SoilMoistureVol_2_0m",
    "et0": "ReferenceET0",
}

VISUAL_CROSSING_BASE_FIELDS = [
    "tempmax",
    "tempmin",
    "temp",
    "precip",
    "snow",
    "humidity",
    "windspeed",
]


class WeatherSource(Enum):
    """Supported upstream weather providers."""

    METEOSTAT = "Meteostat"
    OPEN_METEO = "Open-Meteo"
    NOAA = "NOAA CDO"
    VISUAL_CROSSING = "Visual Crossing"


class WeatherDataError(RuntimeError):
    """Raised when weather data cannot be fetched or processed."""


def normalize_providers(
    providers: Optional[Iterable[str | WeatherSource]],
) -> list[WeatherSource]:
    """Coerce provider inputs into a list of WeatherSource enums."""

    if not providers:
        return list(WeatherSource)

    normalized: list[WeatherSource] = []
    for provider in providers:
        if isinstance(provider, WeatherSource):
            normalized.append(provider)
            continue

        try:
            normalized.append(WeatherSource(provider))
        except ValueError as exc:
            valid = ", ".join(source.value for source in WeatherSource)
            raise WeatherDataError(
                f"Unsupported provider '{provider}'. Choose from: {valid}."
            ) from exc

    return normalized


@dataclass
class Location:
    """Physical location resolved via geocoding."""

    name: str
    latitude: float
    longitude: float

    def to_point(self) -> Point:
        return Point(self.latitude, self.longitude)


@dataclass
class LocalWeatherGPTResult:
    """Container for processed results."""

    combined: pd.DataFrame
    by_source: Dict[str, pd.DataFrame]
    forecast: Optional[pd.DataFrame]
    annual_stats: pd.DataFrame
    monthly_stats: pd.DataFrame
    frost_days: pd.DataFrame
    heatwave_days: pd.DataFrame
    gdd: pd.DataFrame
    drought_risk: pd.DataFrame
    charts: Dict[str, str]
    crop_recommendations: str
    planning_guidance: str


# -------------------------------
# Geocoding utilities
# -------------------------------

def geocode_location(location: str) -> Location:
    """Geocode a human-readable location string into coordinates.

    Falls back to Buchanan, MI when geocoding fails to keep the pipeline running.
    """

    parts = [segment.strip() for segment in location.split(",")]
    if len(parts) == 2:
        try:
            latitude = float(parts[0])
            longitude = float(parts[1])
        except ValueError:
            pass
        else:
            if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                return Location(name=location, latitude=latitude, longitude=longitude)

    geolocator = Nominatim(user_agent=GEOCODER_USER_AGENT)

    try:
        geo = geolocator.geocode(location)
    except GeopyError as exc:  # pragma: no cover - network failures are expected in CI
        raise WeatherDataError(f"Geocoding failed for '{location}': {exc}") from exc

    if geo is None:
        raise WeatherDataError(
            f"Unable to geocode '{location}'. Try specifying latitude and longitude."
        )

    return Location(name=location, latitude=geo.latitude, longitude=geo.longitude)


# -------------------------------
# Credential utilities
# -------------------------------

def _normalize_secret(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        trimmed = value.strip()
        return trimmed or None
    return str(value).strip() or None


def _prompt_secret(label: str) -> str:
    try:
        return getpass.getpass(label)
    except Exception:
        try:
            return input(label)
        except EOFError:
            return ""


def prompt_for_missing_credentials(
    visual_crossing_key: Optional[str],
    noaa_token: Optional[str],
    *,
    prompt_visual_crossing: bool = True,
    prompt_noaa: bool = True,
) -> tuple[Optional[str], Optional[str]]:
    """Request API credentials from the user when they are absent."""

    visual_crossing_key = _normalize_secret(visual_crossing_key)
    noaa_token = _normalize_secret(noaa_token)

    if prompt_visual_crossing and not visual_crossing_key:
        entered = _prompt_secret("Enter Visual Crossing API key (leave blank to skip): ")
        visual_crossing_key = _normalize_secret(entered)

    if prompt_noaa and not noaa_token:
        entered = _prompt_secret("Enter NOAA CDO token (leave blank to skip): ")
        noaa_token = _normalize_secret(entered)

    return visual_crossing_key, noaa_token


def ensure_api_credentials(
    visual_crossing_key: Optional[str],
    noaa_token: Optional[str],
    *,
    require_visual_crossing: bool = False,
    require_noaa: bool = False,
) -> tuple[Optional[str], Optional[str]]:
    """Normalize and validate credential requirements for downstream calls."""

    visual_crossing_key = _normalize_secret(visual_crossing_key)
    noaa_token = _normalize_secret(noaa_token)

    missing: list[str] = []
    if require_visual_crossing and not visual_crossing_key:
        missing.append("Visual Crossing API key")
    if require_noaa and not noaa_token:
        missing.append("NOAA CDO token")

    if missing:
        raise WeatherDataError(
            "Missing required credential(s): "
            + ", ".join(missing)
            + ". Provide them via environment variables, CLI flags, or interactive prompts."
        )

    return visual_crossing_key, noaa_token


# -------------------------------
# Data acquisition & cleaning
# -------------------------------

def _parse_date(value: str | date | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return parser.parse(str(value))


# -------------------------------
# Data acquisition & normalization
# -------------------------------

def fetch_meteostat_daily(
    location: Location,
    start: datetime,
    end: datetime,
    cache_dir: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch raw daily weather observations from Meteostat."""

    try:
        daily = Daily(location.to_point(), start, end)
        if cache_dir:
            daily.cache = os.path.abspath(cache_dir)
        df = daily.fetch().reset_index()
    except Exception as exc:  # pragma: no cover - network dependent
        raise WeatherDataError(
            f"Failed to download Meteostat data for {location.name}: {exc}"
        ) from exc

    if df.empty:
        raise WeatherDataError(
            f"No Meteostat data returned for {location.name} between {start.date()} and {end.date()}."
        )

    return df


def standardize_meteostat(df: pd.DataFrame) -> pd.DataFrame:
    """Convert Meteostat schema to unified analytics columns."""

    cleaned = df.copy()
    cleaned.rename(
        columns={
            "time": "Date",
            "tmax": "High_C",
            "tmin": "Low_C",
            "tavg": "Avg_C",
            "prcp": "Rain_mm",
            "snow": "Snow_mm",
            "rhum": "Humidity_pct",
            "wspd": "WindSpeed_mps",
        },
        inplace=True,
    )
    cleaned["Date"] = pd.to_datetime(cleaned["Date"]).dt.tz_localize(None)
    cleaned.sort_values("Date", inplace=True)

    high_c = pd.to_numeric(cleaned.get("High_C"), errors="coerce")
    low_c = pd.to_numeric(cleaned.get("Low_C"), errors="coerce")
    avg_c = pd.to_numeric(cleaned.get("Avg_C"), errors="coerce")
    rain_mm = pd.to_numeric(cleaned.get("Rain_mm"), errors="coerce")
    snow_mm = pd.to_numeric(cleaned.get("Snow_mm"), errors="coerce")
    humidity = pd.to_numeric(cleaned.get("Humidity_pct"), errors="coerce")
    wind_mps = pd.to_numeric(cleaned.get("WindSpeed_mps"), errors="coerce")

    cleaned["High_F"] = high_c * 9 / 5 + 32
    cleaned["Low_F"] = low_c * 9 / 5 + 32
    cleaned["Avg_F"] = avg_c * 9 / 5 + 32
    cleaned["Rain_in"] = rain_mm / 25.4
    cleaned["Snow_in"] = snow_mm / 25.4
    cleaned["Humidity_pct"] = humidity
    cleaned["WindSpeed_mph"] = wind_mps * MPS_TO_MPH

    standardized = cleaned[[
        "Date",
        "High_F",
        "Low_F",
        "Avg_F",
        "Rain_in",
        "Snow_in",
        "Humidity_pct",
        "WindSpeed_mph",
    ]].copy()
    standardized.insert(1, "Source", WeatherSource.METEOSTAT.value)
    return ensure_standard_columns(standardized)


def ensure_standard_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Guarantee presence and ordering of standard analytics columns while retaining extras."""

    output = df.copy()
    for column in STANDARD_COLUMNS:
        if column not in output:
            output[column] = np.nan

    ordered_columns = list(STANDARD_COLUMNS)
    for column in output.columns:
        if column not in STANDARD_COLUMNS:
            ordered_columns.append(column)

    return output[ordered_columns]


def fetch_open_meteo_daily(location: Location, start: datetime, end: datetime) -> pd.DataFrame:
    """Fetch daily metrics from Open-Meteo archive API."""

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "start_date": start.date().isoformat(),
        "end_date": end.date().isoformat(),
        "timezone": "UTC",
        "daily": (
            "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
            "precipitation_sum,snowfall_sum,relative_humidity_2m_mean,"
            "windspeed_10m_max"
        ),
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
        "windspeed_unit": "mph",
    }

    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network dependent
        raise WeatherDataError(
            f"Failed to download Open-Meteo data for {location.name}: {exc}"
        ) from exc

    payload = response.json()
    daily = payload.get("daily")
    if not daily:
        raise WeatherDataError(
            f"Open-Meteo returned no daily data for {location.name}."
        )

    df = pd.DataFrame(daily)
    df.rename(
        columns={
            "time": "Date",
            "temperature_2m_max": "High_F",
            "temperature_2m_min": "Low_F",
            "temperature_2m_mean": "Avg_F",
            "precipitation_sum": "Rain_in",
            "snowfall_sum": "Snow_in",
            "relative_humidity_2m_mean": "Humidity_pct",
            "windspeed_10m_max": "WindSpeed_mph",
        },
        inplace=True,
    )
    df["Date"] = pd.to_datetime(df["Date"])
    df.insert(1, "Source", WeatherSource.OPEN_METEO.value)
    return ensure_standard_columns(df)


def fetch_open_meteo_forecast(location: Location, forecast_days: int) -> pd.DataFrame:
    """Fetch forward-looking daily forecast metrics from Open-Meteo."""

    if forecast_days <= 0:
        raise WeatherDataError("forecast_days must be positive for Open-Meteo forecast")

    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "forecast_days": forecast_days,
        "timezone": "UTC",
        "daily": (
            "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
            "precipitation_sum,probability_of_precipitation_max,"
            "windspeed_10m_max"
        ),
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
        "windspeed_unit": "mph",
    }

    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network dependent
        raise WeatherDataError(
            f"Failed to download Open-Meteo forecast for {location.name}: {exc}"
        ) from exc

    payload = response.json()
    daily = payload.get("daily")
    if not daily:
        raise WeatherDataError(
            f"Open-Meteo returned no forecast data for {location.name}."
        )

    df = pd.DataFrame(daily)
    rename_map = {
        "time": "Date",
        "temperature_2m_max": "High_F",
        "temperature_2m_min": "Low_F",
        "temperature_2m_mean": "Avg_F",
        "precipitation_sum": "Rain_in",
        "probability_of_precipitation_max": "Rain_Prob_pct",
        "windspeed_10m_max": "WindSpeed_mph",
    }
    df.rename(columns=rename_map, inplace=True)
    df["Date"] = pd.to_datetime(df["Date"])
    df.insert(1, "Source", f"{WeatherSource.OPEN_METEO.value} Forecast")
    return ensure_standard_columns(df)


def fetch_visual_crossing_daily(
    location: Location,
    start: datetime,
    end: datetime,
    api_key: str,
) -> pd.DataFrame:
    """Fetch daily weather from Visual Crossing timeline API."""

    if not api_key:
        raise WeatherDataError(
            "Visual Crossing API key missing. Set VISUAL_CROSSING_API_KEY or pass api_key explicitly."
        )

    base_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
    url = f"{base_url}/{location.latitude},{location.longitude}/{start.date()}/{end.date()}"
    elements = ",".join(VISUAL_CROSSING_BASE_FIELDS + list(VISUAL_CROSSING_OPTIONAL_FIELDS.keys()))
    params = {
        "unitGroup": "us",
        "include": "events,minutes,current,alerts,days",
        "elements": elements,
        "options": "minuteinterval_5",
        "key": api_key,
        "contentType": "json",
    }

    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network dependent
        raise WeatherDataError(
            f"Failed to download Visual Crossing data for {location.name}: {exc}"
        ) from exc

    payload = response.json()
    days = payload.get("days")
    if not days:
        raise WeatherDataError(
            f"Visual Crossing returned no daily data for {location.name}."
        )

    df = pd.DataFrame(days)
    rename_map = {
        "datetime": "Date",
        "tempmax": "High_F",
        "tempmin": "Low_F",
        "temp": "Avg_F",
        "precip": "Rain_in",
        "snow": "Snow_in",
        "humidity": "Humidity_pct",
        "windspeed": "WindSpeed_mph",
    }
    df.rename(columns=rename_map, inplace=True)

    for raw_name, cleaned_name in VISUAL_CROSSING_OPTIONAL_FIELDS.items():
        if raw_name in df.columns:
            df.rename(columns={raw_name: cleaned_name}, inplace=True)
        else:
            df[cleaned_name] = np.nan

    numeric_columns = [
        "High_F",
        "Low_F",
        "Avg_F",
        "Rain_in",
        "Snow_in",
        "Humidity_pct",
        "WindSpeed_mph",
    ] + list(VISUAL_CROSSING_OPTIONAL_FIELDS.values())

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df["Date"] = pd.to_datetime(df["Date"])
    df.insert(1, "Source", WeatherSource.VISUAL_CROSSING.value)
    return ensure_standard_columns(df)


def fetch_visual_crossing_forecast(
    location: Location,
    forecast_days: int,
    api_key: str,
) -> pd.DataFrame:
    """Fetch forward-looking forecast from Visual Crossing."""

    if not api_key:
        raise WeatherDataError(
            "Visual Crossing API key missing. Set VISUAL_CROSSING_API_KEY or pass api_key explicitly."
        )
    if forecast_days <= 0:
        raise WeatherDataError("forecast_days must be positive for Visual Crossing forecast")

    start_date = datetime.utcnow().date()
    end_date = start_date + timedelta(days=forecast_days - 1)

    base_url = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
    url = f"{base_url}/{location.latitude},{location.longitude}/{start_date}/{end_date}"
    elements = ",".join(
        VISUAL_CROSSING_BASE_FIELDS
        + ["precipprob"]
        + list(VISUAL_CROSSING_OPTIONAL_FIELDS.keys())
    )
    params = {
        "unitGroup": "us",
        "include": "events,days,current,alerts",
        "elements": elements,
        "options": "nonulls",
        "key": api_key,
        "contentType": "json",
    }

    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network dependent
        raise WeatherDataError(
            f"Failed to download Visual Crossing forecast for {location.name}: {exc}"
        ) from exc

    payload = response.json()
    days = payload.get("days")
    if not days:
        raise WeatherDataError(
            f"Visual Crossing returned no forecast data for {location.name}."
        )

    df = pd.DataFrame(days)
    rename_map = {
        "datetime": "Date",
        "tempmax": "High_F",
        "tempmin": "Low_F",
        "temp": "Avg_F",
        "precip": "Rain_in",
        "snow": "Snow_in",
        "humidity": "Humidity_pct",
        "windspeed": "WindSpeed_mph",
        "precipprob": "Rain_Prob_pct",
    }
    df.rename(columns=rename_map, inplace=True)

    for raw_name, cleaned_name in VISUAL_CROSSING_OPTIONAL_FIELDS.items():
        if raw_name in df.columns:
            df.rename(columns={raw_name: cleaned_name}, inplace=True)
        else:
            df[cleaned_name] = np.nan

    numeric_columns = [
        "High_F",
        "Low_F",
        "Avg_F",
        "Rain_in",
        "Snow_in",
        "Humidity_pct",
        "WindSpeed_mph",
        "Rain_Prob_pct",
    ] + list(VISUAL_CROSSING_OPTIONAL_FIELDS.values())

    for column in numeric_columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df["Date"] = pd.to_datetime(df["Date"])
    df.insert(1, "Source", "Visual Crossing Forecast")
    return ensure_standard_columns(df)


def _fetch_noaa_station(location: Location, token: str) -> str:
    url = "https://www.ncdc.noaa.gov/cdo-web/api/v2/stations"
    params = {
        "datasetid": "GHCND",
        "limit": 1,
        "sortfield": "distance",
        "latitude": location.latitude,
        "longitude": location.longitude,
    }
    headers = {"token": token}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:  # pragma: no cover - network dependent
        raise WeatherDataError(
            f"Failed to resolve NOAA station near {location.name}: {exc}"
        ) from exc
    data = response.json()
    results = data.get("results") or []
    if not results:
        raise WeatherDataError(
            f"No NOAA stations found near {location.name}. Provide NOAA_STATION_ID manually."
        )
    return results[0]["id"]


def fetch_noaa_daily(
    location: Location,
    start: datetime,
    end: datetime,
    token: str,
    station_id: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch daily weather from NOAA CDO API (GHCND dataset)."""

    if not token:
        raise WeatherDataError(
            "NOAA API token missing. Set NOAA_TOKEN or pass token explicitly."
        )

    station = station_id or _fetch_noaa_station(location, token)

    base_url = "https://www.ncdc.noaa.gov/cdo-web/api/v2/data"
    headers = {"token": token}

    params = {
        "datasetid": "GHCND",
        "stationid": station,
        "startdate": start.date().isoformat(),
        "enddate": end.date().isoformat(),
        "datatypeid": "TMAX,TMIN,PRCP,SNOW,SNWD",
        "units": "standard",
        "limit": 1000,
        "offset": 1,
        "includemetadata": "false",
    }

    records = []
    while True:
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=60)
            if response.status_code == 429:  # pragma: no cover - network dependent
                raise WeatherDataError(
                    "NOAA API rate limit exceeded. Try a smaller range or later."
                )
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - network dependent
            raise WeatherDataError(
                f"Failed to download NOAA data for station {station}: {exc}"
            ) from exc
        payload = response.json()
        batch = payload.get("results") or []
        if not batch:
            break
        records.extend(batch)
        if len(batch) < params["limit"]:
            break
        params["offset"] += params["limit"]

    if not records:
        raise WeatherDataError(
            f"NOAA returned no data for station {station} between {start.date()} and {end.date()}."
        )

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    pivot = df.pivot_table(index="date", columns="datatype", values="value", aggfunc="first")
    pivot.rename(
        columns={
            "TMAX": "High_F",
            "TMIN": "Low_F",
            "PRCP": "Rain_in",
            "SNOW": "Snow_in",
        },
        inplace=True,
    )
    pivot["Avg_F"] = (pivot.get("High_F") + pivot.get("Low_F")) / 2
    pivot["Humidity_pct"] = np.nan
    pivot["WindSpeed_mph"] = np.nan
    pivot.reset_index(inplace=True)
    pivot.rename(columns={"date": "Date"}, inplace=True)
    pivot.insert(1, "Source", WeatherSource.NOAA.value)
    return ensure_standard_columns(pivot)


def fetch_all_sources(
    location: Location,
    start: str | date | datetime,
    end: str | date | datetime,
    cache_dir: Optional[str],
    visual_crossing_key: Optional[str],
    noaa_token: Optional[str],
    noaa_station_id: Optional[str],
    *,
    providers: Iterable[WeatherSource],
) -> Dict[str, pd.DataFrame]:
    """Fetch and standardize data from all configured providers."""

    start_dt, end_dt = _parse_date(start), _parse_date(end)
    if start_dt > end_dt:
        raise ValueError("start date must be on or before end date")

    provider_set = set(providers)
    datasets: Dict[str, pd.DataFrame] = {}

    if WeatherSource.METEOSTAT in provider_set:
        meteostat_raw = fetch_meteostat_daily(location, start_dt, end_dt, cache_dir)
        datasets[WeatherSource.METEOSTAT.value] = standardize_meteostat(meteostat_raw)

    if WeatherSource.OPEN_METEO in provider_set:
        datasets[WeatherSource.OPEN_METEO.value] = fetch_open_meteo_daily(
            location, start_dt, end_dt
        )

    if WeatherSource.VISUAL_CROSSING in provider_set:
        datasets[WeatherSource.VISUAL_CROSSING.value] = fetch_visual_crossing_daily(
            location,
            start_dt,
            end_dt,
            api_key=visual_crossing_key or "",
        )

    if WeatherSource.NOAA in provider_set:
        datasets[WeatherSource.NOAA.value] = fetch_noaa_daily(
            location,
            start_dt,
            end_dt,
            token=noaa_token or "",
            station_id=noaa_station_id,
        )

    if not datasets:
        raise WeatherDataError(
            "No datasets fetched. Confirm provider selections and credential configuration."
        )

    for key, df in datasets.items():
        df.sort_values("Date", inplace=True)
        df.reset_index(drop=True, inplace=True)

    return datasets


def collect_forecasts(
    location: Location,
    forecast_days: int,
    visual_crossing_key: Optional[str],
) -> Optional[pd.DataFrame]:
    """Fetch available forecast feeds and merge into a single table."""

    if forecast_days <= 0:
        return None

    frames: list[pd.DataFrame] = []

    try:
        frames.append(fetch_open_meteo_forecast(location, forecast_days))
    except WeatherDataError as exc:
        logging.warning("Open-Meteo forecast unavailable: %s", exc)

    if visual_crossing_key:
        try:
            frames.append(
                fetch_visual_crossing_forecast(location, forecast_days, visual_crossing_key)
            )
        except WeatherDataError as exc:
            logging.warning("Visual Crossing forecast unavailable: %s", exc)

    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True, sort=False)
    combined.sort_values(["Date", "Source"], inplace=True)
    combined.reset_index(drop=True, inplace=True)
    return combined


# -------------------------------
# Metrics & statistics
# -------------------------------

def calculate_climate_metrics(df: pd.DataFrame, base_temp_f: float) -> Dict[str, pd.DataFrame]:
    """Derive yearly and monthly statistics plus agro-climate indicators."""

    metrics = df.copy()
    metrics.sort_values(["Source", "Date"], inplace=True)
    metrics["Year"] = metrics["Date"].dt.year
    metrics["Month_Period"] = metrics["Date"].dt.to_period("M")
    metrics["GDD"] = np.maximum(
        0.0, ((metrics["High_F"] + metrics["Low_F"]) / 2) - base_temp_f
    )

    metrics["Frost_Day"] = metrics["Low_F"] <= 32
    metrics["Heatwave_Day"] = metrics["High_F"] >= 90
    metrics["Dry_Day"] = metrics["Rain_in"].fillna(0) < 0.1

    annual = (
        metrics.groupby(["Source", "Year"], as_index=False)
        .agg(
            High_F_max=("High_F", "max"),
            High_F_mean=("High_F", "mean"),
            High_F_min=("High_F", "min"),
            Low_F_mean=("Low_F", "mean"),
            Rain_in_total=("Rain_in", "sum"),
            Rain_in_mean=("Rain_in", "mean"),
            Humidity_pct_mean=("Humidity_pct", "mean"),
            GDD_total=("GDD", "sum"),
            Frost_Days=("Frost_Day", "sum"),
            Heatwave_Days=("Heatwave_Day", "sum"),
            Dry_Days=("Dry_Day", "sum"),
        )
    )

    monthly = (
        metrics.groupby(["Source", "Month_Period"], as_index=False)
        .agg(
            High_F_max=("High_F", "max"),
            High_F_mean=("High_F", "mean"),
            Low_F_mean=("Low_F", "mean"),
            Rain_in_total=("Rain_in", "sum"),
            Humidity_pct_mean=("Humidity_pct", "mean"),
            GDD_total=("GDD", "sum"),
            Frost_Days=("Frost_Day", "sum"),
            Heatwave_Days=("Heatwave_Day", "sum"),
            Dry_Days=("Dry_Day", "sum"),
        )
    )
    monthly.rename(columns={"Month_Period": "Month"}, inplace=True)
    monthly["Month"] = pd.to_datetime(monthly["Month"].astype(str)) + MonthEnd(0)

    frost_days = metrics.loc[metrics["Frost_Day"], ["Date", "Source", "Low_F"]]
    heatwave_days = metrics.loc[metrics["Heatwave_Day"], ["Date", "Source", "High_F"]]

    gdd = metrics[["Date", "Source", "GDD"]]

    # Drought risk: longest consecutive dry spell per year and source
    dry_blocks = metrics.copy()
    dry_blocks["Dry_Block"] = dry_blocks.groupby("Source")["Dry_Day"].transform(
        lambda series: (series != series.shift()).cumsum()
    )
    drought_risk = (
        dry_blocks.loc[dry_blocks["Dry_Day"]]
        .groupby(["Source", "Year", "Dry_Block"]).size()
        .reset_index(name="Consecutive_Dry_Days")
    )
    drought_risk = (
        drought_risk.groupby(["Source", "Year"], as_index=False)["Consecutive_Dry_Days"].max()
    )

    return {
        "annual": annual,
        "monthly": monthly,
        "frost_days": frost_days,
        "heatwave_days": heatwave_days,
        "gdd": gdd,
        "drought_risk": drought_risk,
    }


# -------------------------------
# Visualization helpers
# -------------------------------

def create_visualizations(df: pd.DataFrame, output_dir: str) -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    sns.set_theme(style="whitegrid")

    charts: Dict[str, str] = {}

    def _save(fig: plt.Figure, name: str) -> str:
        path = os.path.join(output_dir, name)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        charts[name] = path
        return path

    def _plot_line(metric: str, ylabel: str, title: str, filename: str) -> None:
        pivot = df.pivot_table(index="Date", columns="Source", values=metric, aggfunc="mean")
        pivot = pivot.dropna(how="all", axis=1)
        if pivot.empty:
            return
        fig, ax = plt.subplots(figsize=(10, 5))
        pivot.plot(ax=ax)
        ax.set_title(title)
        ax.set_xlabel("Date")
        ax.set_ylabel(ylabel)
        ax.legend(loc="best", title="Source")
        _save(fig, filename)

    _plot_line("High_F", "Temperature (°F)", "Daily High Temperature by Source", "temperature_high_trend.png")
    _plot_line("Low_F", "Temperature (°F)", "Daily Low Temperature by Source", "temperature_low_trend.png")
    _plot_line("Rain_in", "Rainfall (inches)", "Daily Rainfall by Source", "rainfall_trend.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.histplot(df, x="High_F", hue="Source", bins=30, ax=ax, element="step", stat="density", common_norm=False)
    ax.set_title("Distribution of Daily High Temperatures by Source")
    ax.set_xlabel("High (°F)")
    _save(fig, "high_temp_hist.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.scatterplot(data=df, x="Rain_in", y="High_F", hue="Source", ax=ax)
    ax.set_title("Rainfall vs. High Temperature by Source")
    ax.set_xlabel("Rainfall (inches)")
    ax.set_ylabel("High (°F)")
    ax.legend(loc="best", title="Source")
    _save(fig, "rain_vs_temp_scatter.png")

    return charts


# -------------------------------
# Crop recommendation heuristics
# -------------------------------

def suggest_crop_recommendations(annual_stats: pd.DataFrame, drought_risk: pd.DataFrame) -> str:
    if annual_stats.empty:
        return "Insufficient data for crop recommendations."

    overall = annual_stats.groupby("Year").mean(numeric_only=True).reset_index()
    overall.sort_values("Year", inplace=True)

    latest_year = overall.iloc[-1]
    avg_frost_days = overall["Frost_Days"].mean()
    avg_gdd = overall["GDD_total"].mean()
    avg_rain = overall["Rain_in_total"].mean()

    drought_summary = np.nan
    if not drought_risk.empty:
        drought_yearly = drought_risk.groupby("Year")["Consecutive_Dry_Days"].mean().reset_index()
        drought_summary = drought_yearly["Consecutive_Dry_Days"].mean()

    insights = [
        f"Average growing degree days: {avg_gdd:,.0f} (base 50°F).",
        f"Average frost days per year: {avg_frost_days:,.0f}.",
        f"Average annual rainfall: {avg_rain:,.1f} inches.",
    ]

    if not np.isnan(drought_summary):
        insights.append(
            f"Typical longest dry spell: {drought_summary:,.0f} consecutive days."
        )

    if avg_gdd > 2500:
        insights.append(
            "Heat accumulation supports long-season crops like corn and soy; monitor moisture during dry spells."
        )
    elif avg_gdd > 1800:
        insights.append(
            "Favorable for cool-to-warm season vegetables (e.g., beans, squash) with modest frost risk management."
        )
    else:
        insights.append(
            "Shorter growing season suggests focusing on hardy grains, brassicas, and using season extension (high tunnels)."
        )

    if latest_year["Frost_Days"] > avg_frost_days:
        insights.append(
            "Most recent season saw elevated frost days—consider frost-tolerant varieties or row cover investment."
        )

    if latest_year["Heatwave_Days"] > 10:
        insights.append(
            "High heatwave frequency; ensure irrigation scheduling and heat-tolerant cultivars."
        )

    if avg_rain < 30:
        insights.append(
            "Below-average rainfall; evaluate drought-tolerant hybrids and soil moisture conservation (mulching, cover crops)."
        )

    return " ".join(insights)


def generate_planning_guidance(forecast: Optional[pd.DataFrame]) -> str:
    """Translate near-term forecast into actionable guidance."""

    if forecast is None or forecast.empty:
        return (
            "Forecast feed unavailable. Verify API keys or try again later to receive planning guidance."
        )

    frame = forecast.copy()
    frame.sort_values("Date", inplace=True)

    rain_prob = (
        frame["Rain_Prob_pct"] if "Rain_Prob_pct" in frame else pd.Series(0, index=frame.index)
    )

    comfortable = frame[
        (frame["High_F"] >= 55)
        & (frame["High_F"] <= 85)
        & (frame["Rain_in"].fillna(0) < 0.15)
        & (rain_prob.fillna(0) <= 40)
    ]

    planting_low_threshold = 45
    soil_temp_col = None
    for candidate in ["SoilTemp_0_4m_F", "SoilTemp_0_1m_F", "SoilTemp_1_0m_F"]:
        if candidate in frame.columns:
            soil_temp_col = candidate
            break

    if soil_temp_col:
        planting = frame[
            (frame[soil_temp_col] >= 50)
            & (frame["Low_F"] >= planting_low_threshold)
            & (frame["Rain_in"].fillna(0) <= 0.5)
        ]
    else:
        planting = frame[
            (frame["Low_F"] >= planting_low_threshold)
            & (frame["Rain_in"].fillna(0) <= 0.5)
        ]

    frost_risk = frame[frame["Low_F"] <= 32]
    heat_risk = frame[frame["High_F"] >= 90]
    heavy_rain = frame[frame["Rain_in"].fillna(0) >= 1]
    high_wind = frame[frame["WindSpeed_mph"].fillna(0) >= 25]

    messages: list[str] = []

    if not comfortable.empty:
        windows = ", ".join(
            day.strftime("%a %b %d")
            for day in comfortable["Date"].dt.date.iloc[:3]
        )
        messages.append(
            f"Best outdoor field-work windows (dry & mild): {windows}."
        )
    else:
        messages.append("No dry, mild days detected—plan indoor tasks or irrigation maintenance.")

    if not planting.empty:
        planting_days = ", ".join(
            day.strftime("%a %b %d") for day in planting["Date"].dt.date.iloc[:3]
        )
        suffix = (
            f"soil temps ≥ {planting[soil_temp_col].min():.0f}°F"
            if soil_temp_col
            else "overnight lows ≥ 45°F"
        )
        messages.append(
            f"Favorable planting days: {planting_days} ({suffix})."
        )
    else:
        reason = "soil temps remain cool" if soil_temp_col else "overnight lows below 45°F"
        messages.append(
            f"Delay direct seeding—{reason} for the forecast horizon."
        )

    if not frost_risk.empty:
        frost_dates = ", ".join(
            day.strftime("%a %b %d") for day in frost_risk["Date"].dt.date
        )
        messages.append(
            f"Frost risk on {frost_dates}; protect tender crops and cover emerging seedlings."
        )

    if not heavy_rain.empty:
        rain_dates = ", ".join(
            day.strftime("%a %d") for day in heavy_rain["Date"].dt.date
        )
        messages.append(
            f"Expect ≥1"" of rain on {rain_dates}; adjust irrigation and field access plans."
        )

    if not heat_risk.empty:
        heat_dates = ", ".join(
            day.strftime("%a %d") for day in heat_risk["Date"].dt.date
        )
        messages.append(
            f"High heat stress days ({heat_risk['High_F'].max():.0f}°F) forecast around {heat_dates}."
        )

    if not high_wind.empty:
        wind_dates = ", ".join(
            day.strftime("%a %d") for day in high_wind["Date"].dt.date
        )
        messages.append(
            "Winds ≥25 mph expected on {dates}; delay spraying or row-cover installation.".format(
                dates=wind_dates
            )
        )

    return " ".join(messages)
# -------------------------------
# Public API
# -------------------------------

def get_weather_data(
    location: str = DEFAULT_LOCATION,
    start_date: str | date | datetime = "1995-01-01",
    end_date: str | date | datetime = date.today().isoformat(),
    base_temp: float = DEFAULT_BASE_TEMP_F,
    forecast_days: int = DEFAULT_FORECAST_DAYS,
    output_dir: str = "artifacts/weather",
    cache_dir: Optional[str] = None,
    export_csv: Optional[str] = None,
    visual_crossing_key: Optional[str] = None,
    noaa_token: Optional[str] = None,
    noaa_station_id: Optional[str] = None,
    prompt_for_api_keys: bool = False,
    require_visual_crossing_key: bool = False,
    require_noaa_token: bool = False,
    providers: Optional[Iterable[str | WeatherSource]] = None,
) -> LocalWeatherGPTResult:
    """Run the LocalWeatherGPT pipeline and return consolidated analytics.

    Parameters align with CLI flags and allow overriding API credentials. Pass
    `providers` to restrict which upstream services are queried when credentials
    are unavailable or to shorten execution time.
    """

    cache_dir = cache_dir or os.getenv("METEOSTAT_CACHE_DIR")
    visual_crossing_key = visual_crossing_key or VISUAL_CROSSING_API_KEY
    noaa_token = noaa_token or NOAA_TOKEN
    noaa_station_id = noaa_station_id or NOAA_STATION_ID

    active_providers = normalize_providers(providers)
    include_visual_crossing = WeatherSource.VISUAL_CROSSING in active_providers
    include_noaa = WeatherSource.NOAA in active_providers

    if prompt_for_api_keys and (include_visual_crossing or include_noaa):
        visual_crossing_key, noaa_token = prompt_for_missing_credentials(
            visual_crossing_key,
            noaa_token,
            prompt_visual_crossing=include_visual_crossing,
            prompt_noaa=include_noaa,
        )

    visual_crossing_key, noaa_token = ensure_api_credentials(
        visual_crossing_key,
        noaa_token,
        require_visual_crossing=include_visual_crossing and require_visual_crossing_key,
        require_noaa=include_noaa and require_noaa_token,
    )

    if include_visual_crossing and not visual_crossing_key:
        logging.info("Skipping Visual Crossing provider: no API key supplied.")
        active_providers = [p for p in active_providers if p != WeatherSource.VISUAL_CROSSING]
        include_visual_crossing = False

    if include_noaa and not noaa_token:
        logging.info("Skipping NOAA provider: no API token supplied.")
        active_providers = [p for p in active_providers if p != WeatherSource.NOAA]
        include_noaa = False

    if not active_providers:
        raise WeatherDataError(
            "No providers selected. Supply at least one provider or provide the necessary API credentials."
        )

    resolved_location = geocode_location(location)
    datasets = fetch_all_sources(
        resolved_location,
        start_date,
        end_date,
        cache_dir,
        visual_crossing_key,
        noaa_token,
        noaa_station_id,
        providers=active_providers,
    )

    combined = pd.concat(datasets.values(), ignore_index=True)
    combined.sort_values(["Source", "Date"], inplace=True)
    combined.reset_index(drop=True, inplace=True)

    metrics = calculate_climate_metrics(combined, base_temp)
    charts = create_visualizations(combined, output_dir)
    crop_recs = suggest_crop_recommendations(metrics["annual"], metrics["drought_risk"])

    forecast = collect_forecasts(resolved_location, forecast_days, visual_crossing_key)
    if forecast is not None:
        forecast = forecast.copy()
        forecast["GDD"] = np.maximum(
            0.0, ((forecast["High_F"] + forecast["Low_F"]) / 2) - base_temp
        )
    planning_guidance = generate_planning_guidance(forecast)

    if export_csv:
        os.makedirs(os.path.dirname(export_csv) or ".", exist_ok=True)
        combined.to_csv(export_csv, index=False)

    return LocalWeatherGPTResult(
        combined=combined,
        by_source=datasets,
        forecast=forecast,
        annual_stats=metrics["annual"],
        monthly_stats=metrics["monthly"],
        frost_days=metrics["frost_days"],
        heatwave_days=metrics["heatwave_days"],
        gdd=metrics["gdd"],
        drought_risk=metrics["drought_risk"],
        charts=charts,
        crop_recommendations=crop_recs,
        planning_guidance=planning_guidance,
    )


# -------------------------------
# Command-line interface
# -------------------------------

def _cli(argv: Optional[Iterable[str]] = None) -> None:
    sources_text = ", ".join(f"{name} ({url})" for name, url in DATA_SOURCES.items())
    parser_ = argparse.ArgumentParser(
        prog="localweathergpt",
        description=(
            "LocalWeatherGPT: download, analyze, and forecast weather for farm planning.\n"
            f"Data sources: {sources_text}."
        )
    )
    parser_.add_argument("--location", default=DEFAULT_LOCATION, help="City, State or coordinates")
    parser_.add_argument("--start", default="1995-01-01", help="Start date (YYYY-MM-DD)")
    parser_.add_argument("--end", default=date.today().isoformat(), help="End date (YYYY-MM-DD)")
    parser_.add_argument(
        "--base-temp",
        default=DEFAULT_BASE_TEMP_F,
        type=float,
        help="Base temperature for growing degree days (°F)",
    )
    parser_.add_argument(
        "--output-dir",
        default="artifacts/weather",
        help="Directory for generated visualizations",
    )
    parser_.add_argument(
        "--forecast-days",
        default=DEFAULT_FORECAST_DAYS,
        type=int,
        help="Number of upcoming days to fetch for activity/planting guidance",
    )
    parser_.add_argument(
        "--cache-dir",
        default=None,
        help="Optional cache directory for Meteostat downloads",
    )
    parser_.add_argument(
        "--export-csv",
        default=None,
        help="Path to save the enriched dataset as CSV",
    )
    parser_.add_argument(
        "--visual-crossing-key",
        default=None,
        help="Visual Crossing API key (falls back to VISUAL_CROSSING_API_KEY env)",
    )
    parser_.add_argument(
        "--noaa-token",
        default=None,
        help="NOAA CDO token (falls back to NOAA_TOKEN env)",
    )
    parser_.add_argument(
        "--noaa-station",
        default=None,
        help="Optional NOAA station ID to override automatic lookup",
    )
    parser_.add_argument(
        "--prompt-api-keys",
        action="store_true",
        help="Interactively ask for Visual Crossing and NOAA credentials when missing",
    )
    parser_.add_argument(
        "--require-visual-crossing-key",
        action="store_true",
        help="Fail if a Visual Crossing API key is not provided",
    )
    parser_.add_argument(
        "--require-noaa-token",
        action="store_true",
        help="Fail if a NOAA CDO token is not provided",
    )
    parser_.add_argument(
        "--providers",
        nargs="+",
        choices=[source.value for source in WeatherSource],
        help="Optional subset of providers to query (default: all)",
    )

    args = parser_.parse_args(argv)

    try:
        result = get_weather_data(
            location=args.location,
            start_date=args.start,
            end_date=args.end,
            base_temp=args.base_temp,
            forecast_days=args.forecast_days,
            output_dir=args.output_dir,
            cache_dir=args.cache_dir,
            export_csv=args.export_csv,
            visual_crossing_key=args.visual_crossing_key,
            noaa_token=args.noaa_token,
            noaa_station_id=args.noaa_station,
            prompt_for_api_keys=args.prompt_api_keys,
            require_visual_crossing_key=args.require_visual_crossing_key,
            require_noaa_token=args.require_noaa_token,
            providers=args.providers,
        )
    except WeatherDataError as exc:
        parser_.error(str(exc))
    else:
        print(f"LocalWeatherGPT finished processing {args.location}.")
        print("Data sources:")
        for source, frame in result.by_source.items():
            url = DATA_SOURCES.get(source, "")
            suffix = f" ({url})" if url else ""
            print(f"  - {source}{suffix}: {len(frame):,} rows")
        print(f"Total rows fetched: {len(result.combined):,}")
        print(f"Charts saved to {args.output_dir}")
        print("Crop recommendations:")
        print(result.crop_recommendations)
        print("\nActivity & planting guidance:")
        print(result.planning_guidance)


if __name__ == "__main__":  # pragma: no cover
    _cli()
