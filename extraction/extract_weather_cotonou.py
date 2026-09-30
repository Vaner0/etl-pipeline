"""Fetch the previous day's hourly weather for Cotonou and upsert it to Neon."""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
import requests
from dotenv import load_dotenv
from psycopg import sql

LOGGER = logging.getLogger(__name__)
API_URL = "https://archive-api.open-meteo.com/v1/archive"
LOCATION_TIMEZONE = ZoneInfo("Africa/Porto-Novo")
SCHEMA_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
HOURLY_FIELDS: dict[str, type[int] | type[float]] = {
    "temperature_2m": float,
    "relative_humidity_2m": float,
    "precipitation": float,
    "rain": float,
    "weather_code": int,
    "wind_speed_10m": float,
}
CONNECT_MAX_ATTEMPTS = 4
CONNECT_INITIAL_DELAY_SECONDS = 2
CONNECT_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class WeatherRecord:
    observed_at: datetime
    temperature_2m: float | None
    relative_humidity_2m: float | None
    precipitation: float | None
    rain: float | None
    weather_code: int | None
    wind_speed_10m: float | None


def _to_number(value: Any, field_name: str, expected_type: type[int] | type[float]) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Valeur invalide pour {field_name}: {value!r}")
    if expected_type is int:
        if not isinstance(value, int):
            raise ValueError(f"La valeur de {field_name} doit être un entier: {value!r}")
        return value
    return float(value)


def parse_hourly_response(payload: dict[str, Any]) -> list[WeatherRecord]:
    """Validate the API response and map its hourly arrays to typed records."""
    if not isinstance(payload, dict):
        raise ValueError("La réponse Open-Meteo doit être un objet JSON.")
    if payload.get("error"):
        raise RuntimeError(f"Open-Meteo a signalé une erreur: {payload.get('reason', 'raison inconnue')}")

    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("La réponse Open-Meteo ne contient pas d'objet 'hourly' valide.")

    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        raise ValueError("La réponse Open-Meteo ne contient aucune heure.")

    missing_fields = [field for field in HOURLY_FIELDS if field not in hourly]
    if missing_fields:
        raise ValueError(f"Champs horaires absents de la réponse: {', '.join(missing_fields)}")

    for field in HOURLY_FIELDS:
        values = hourly[field]
        if not isinstance(values, list) or len(values) != len(times):
            raise ValueError(f"Le tableau '{field}' est absent ou de longueur incohérente.")

    records: list[WeatherRecord] = []
    for index, timestamp in enumerate(times):
        if not isinstance(timestamp, str):
            raise ValueError(f"Horodatage invalide à l'index {index}: {timestamp!r}")
        try:
            observed_at = datetime.fromisoformat(timestamp)
        except ValueError as exc:
            raise ValueError(f"Horodatage ISO invalide à l'index {index}: {timestamp!r}") from exc
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=LOCATION_TIMEZONE)

        values = {
            field: _to_number(hourly[field][index], field, expected_type)
            for field, expected_type in HOURLY_FIELDS.items()
        }
        records.append(WeatherRecord(observed_at=observed_at, **values))

    return records


def fetch_weather_records(target_date: date, http_get: Any = requests.get) -> list[WeatherRecord]:
    """Fetch one calendar day of hourly observations from the Open-Meteo archive."""
    response = http_get(
        API_URL,
        params={
            "latitude": 6.3703,
            "longitude": 2.3912,
            "start_date": target_date.isoformat(),
            "end_date": target_date.isoformat(),
            "hourly": ",".join(HOURLY_FIELDS),
            "timezone": str(LOCATION_TIMEZONE),
        },
        timeout=30,
    )
    response.raise_for_status()
    return parse_hourly_response(response.json())


def _validate_schema(schema: str) -> None:
    if not SCHEMA_PATTERN.fullmatch(schema):
        raise ValueError(
            "ETL_SCHEMA doit être un identifiant SQL simple "
            "(lettres, chiffres et underscores, sans espace)."
        )


def load_weather_records(
    records: list[WeatherRecord],
    database_url: str,
    schema: str = "etl_pipeline",
    *,
    max_attempts: int = CONNECT_MAX_ATTEMPTS,
    initial_delay_seconds: int = CONNECT_INITIAL_DELAY_SECONDS,
    sleep: Any = time.sleep,
) -> int:
    """Create the destination table if needed and idempotently upsert records."""
    if not records:
        raise ValueError("Aucune observation à charger; la table n'a pas été modifiée.")
    if not database_url.strip():
        raise ValueError("DATABASE_URL ne peut pas être vide.")
    _validate_schema(schema)
    if max_attempts < 1:
        raise ValueError("max_attempts doit être supérieur ou égal à 1.")
    if initial_delay_seconds < 0:
        raise ValueError("initial_delay_seconds ne peut pas être négatif.")

    create_schema = sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
    create_table = sql.SQL(
        """
        CREATE TABLE IF NOT EXISTS {}.staging_weather_cotonou (
            observed_at TIMESTAMPTZ PRIMARY KEY,
            temperature_2m DOUBLE PRECISION,
            relative_humidity_2m DOUBLE PRECISION,
            precipitation DOUBLE PRECISION,
            rain DOUBLE PRECISION,
            weather_code INTEGER,
            wind_speed_10m DOUBLE PRECISION,
            loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    ).format(sql.Identifier(schema))
    upsert = sql.SQL(
        """
        INSERT INTO {}.staging_weather_cotonou (
            observed_at,
            temperature_2m,
            relative_humidity_2m,
            precipitation,
            rain,
            weather_code,
            wind_speed_10m
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (observed_at) DO UPDATE SET
            temperature_2m = EXCLUDED.temperature_2m,
            relative_humidity_2m = EXCLUDED.relative_humidity_2m,
            precipitation = EXCLUDED.precipitation,
            rain = EXCLUDED.rain,
            weather_code = EXCLUDED.weather_code,
            wind_speed_10m = EXCLUDED.wind_speed_10m,
            loaded_at = CURRENT_TIMESTAMP
        """
    ).format(sql.Identifier(schema))
    parameters = [
        (
            record.observed_at,
            record.temperature_2m,
            record.relative_humidity_2m,
            record.precipitation,
            record.rain,
            record.weather_code,
            record.wind_speed_10m,
        )
        for record in records
    ]

    for attempt in range(1, max_attempts + 1):
        try:
            with psycopg.connect(
                conninfo=database_url,
                connect_timeout=CONNECT_TIMEOUT_SECONDS,
            ) as connection:
                connection.execute(create_schema)
                connection.execute(create_table)
                with connection.cursor() as cursor:
                    cursor.executemany(upsert, parameters)
            LOGGER.info("Chargement terminé: %d observation(s) dans %s.staging_weather_cotonou.", len(records), schema)
            return len(records)
        except (psycopg.OperationalError, psycopg.InterfaceError):
            if attempt == max_attempts:
                LOGGER.exception("Connexion PostgreSQL impossible après %d tentative(s).", max_attempts)
                raise
            delay = min(initial_delay_seconds * (2 ** (attempt - 1)), 30)
            LOGGER.warning(
                "Connexion PostgreSQL échouée (tentative %d/%d); nouvel essai dans %d seconde(s).",
                attempt,
                max_attempts,
                delay,
            )
            sleep(delay)

    raise RuntimeError("Le chargement s'est terminé sans résultat inattendu.")


def run() -> int:
    """Run yesterday's extraction and load it into the configured PostgreSQL database."""
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL est absent; configurez-le dans le fichier .env.")

    schema = os.getenv("ETL_SCHEMA", "etl_pipeline")
    target_date = datetime.now(LOCATION_TIMEZONE).date() - timedelta(days=1)
    LOGGER.info("Extraction de la météo de Cotonou pour le %s.", target_date.isoformat())
    records = fetch_weather_records(target_date)
    LOGGER.info("Open-Meteo a renvoyé %d observation(s).", len(records))
    return load_weather_records(records, database_url, schema)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    loaded_count = run()
    LOGGER.info("Pipeline météo terminé; %d observation(s) chargée(s).", loaded_count)


if __name__ == "__main__":
    main()
