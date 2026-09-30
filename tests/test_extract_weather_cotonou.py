from __future__ import annotations

import unittest
from datetime import date, datetime
from typing import Any
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import psycopg

from extraction.extract_weather_cotonou import (
    HOURLY_FIELDS,
    WeatherRecord,
    fetch_weather_records,
    load_weather_records,
    parse_hourly_response,
)


def make_payload() -> dict[str, Any]:
    hourly: dict[str, list[object]] = {
        "time": ["2026-09-29T00:00", "2026-09-29T01:00"],
        "temperature_2m": [27.5, 27.0],
        "relative_humidity_2m": [82, 84],
        "precipitation": [0.0, 0.2],
        "rain": [0.0, 0.2],
        "weather_code": [1, 61],
        "wind_speed_10m": [8.4, 7.9],
    }
    return {"hourly": hourly}


class ParseHourlyResponseTests(unittest.TestCase):
    def test_maps_hourly_arrays_to_timezone_aware_records(self) -> None:
        records = parse_hourly_response(make_payload())

        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].temperature_2m, 27.5)
        self.assertEqual(records[0].weather_code, 1)
        self.assertEqual(records[0].observed_at.tzinfo, ZoneInfo("Africa/Porto-Novo"))

    def test_rejects_missing_field(self) -> None:
        payload = make_payload()
        del payload["hourly"]["rain"]

        with self.assertRaisesRegex(ValueError, "Champs horaires absents"):
            parse_hourly_response(payload)

    def test_rejects_inconsistent_array_lengths(self) -> None:
        payload = make_payload()
        payload["hourly"]["rain"].pop()

        with self.assertRaisesRegex(ValueError, "longueur incohérente"):
            parse_hourly_response(payload)

    def test_rejects_non_numeric_weather_values(self) -> None:
        payload = make_payload()
        payload["hourly"]["temperature_2m"][0] = "chaud"

        with self.assertRaisesRegex(ValueError, "Valeur invalide"):
            parse_hourly_response(payload)

    def test_rejects_api_error_payload(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "Open-Meteo"):
            parse_hourly_response({"error": True, "reason": "date not available"})


class FetchWeatherRecordsTests(unittest.TestCase):
    def test_requests_the_requested_local_day_and_parses_response(self) -> None:
        response = MagicMock()
        response.json.return_value = make_payload()
        http_get = MagicMock(return_value=response)

        records = fetch_weather_records(date(2026, 9, 29), http_get=http_get)

        response.raise_for_status.assert_called_once_with()
        self.assertEqual(len(records), 2)
        self.assertEqual(http_get.call_args.kwargs["params"]["start_date"], "2026-09-29")
        self.assertEqual(http_get.call_args.kwargs["params"]["end_date"], "2026-09-29")
        self.assertEqual(
            http_get.call_args.kwargs["params"]["hourly"],
            ",".join(HOURLY_FIELDS),
        )
        self.assertEqual(http_get.call_args.kwargs["timeout"], 30)

    def test_propagates_http_errors(self) -> None:
        response = MagicMock()
        response.raise_for_status.side_effect = ValueError("HTTP 503")

        with self.assertRaisesRegex(ValueError, "503"):
            fetch_weather_records(date(2026, 9, 29), http_get=MagicMock(return_value=response))


class LoadWeatherRecordsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = [
            WeatherRecord(
                observed_at=datetime(2026, 9, 29, hour, tzinfo=ZoneInfo("Africa/Porto-Novo")),
                temperature_2m=27.5,
                relative_humidity_2m=82.0,
                precipitation=0.0,
                rain=0.0,
                weather_code=1,
                wind_speed_10m=8.4,
            )
            for hour in (0, 1)
        ]

    @patch("extraction.extract_weather_cotonou.psycopg.connect")
    def test_creates_schema_and_table_then_upserts_rows(self, connect: MagicMock) -> None:
        connection = MagicMock()
        connection.__enter__.return_value = connection
        cursor = MagicMock()
        connection.cursor.return_value.__enter__.return_value = cursor
        connect.return_value = connection

        loaded = load_weather_records(self.records, "postgresql://example", "etl_pipeline")

        self.assertEqual(loaded, 2)
        connect.assert_called_once_with(
            conninfo="postgresql://example",
            connect_timeout=15,
        )
        self.assertEqual(connection.execute.call_count, 2)
        cursor.executemany.assert_called_once()
        self.assertEqual(len(cursor.executemany.call_args.args[1]), 2)

    @patch("extraction.extract_weather_cotonou.psycopg.connect")
    def test_retries_transient_connection_failures_with_backoff(self, connect: MagicMock) -> None:
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.cursor.return_value.__enter__.return_value = MagicMock()
        connect.side_effect = [psycopg.OperationalError("cold start"), connection]
        sleep = MagicMock()

        loaded = load_weather_records(
            self.records,
            "postgresql://example",
            max_attempts=3,
            initial_delay_seconds=2,
            sleep=sleep,
        )

        self.assertEqual(loaded, 2)
        self.assertEqual(connect.call_count, 2)
        sleep.assert_called_once_with(2)

    @patch("extraction.extract_weather_cotonou.psycopg.connect")
    def test_does_not_connect_when_no_records_are_provided(self, connect: MagicMock) -> None:
        with self.assertRaisesRegex(ValueError, "Aucune observation"):
            load_weather_records([], "postgresql://example")

        connect.assert_not_called()

    @patch("extraction.extract_weather_cotonou.psycopg.connect")
    def test_rejects_unsafe_schema_names_before_connecting(self, connect: MagicMock) -> None:
        with self.assertRaisesRegex(ValueError, "ETL_SCHEMA"):
            load_weather_records(self.records, "postgresql://example", "bad-name; DROP SCHEMA public")

        connect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
