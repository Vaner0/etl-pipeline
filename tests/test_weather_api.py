from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.main import app


class WeatherApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_health_endpoint_reports_service_liveness(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("api.main.fetch_monthly_weather_payload")
    def test_monthly_endpoint_returns_public_payload_without_cache(
        self,
        fetch_payload: MagicMock,
    ) -> None:
        payload = {
            "metadata": {
                "generated_at": "2026-10-04T18:20:03+00:00",
                "source": "dbt_marts.mart_weather_cotonou_monthly",
                "dataset": "Open-Meteo Archive API — Cotonou, Bénin",
                "note": "Monthly values are partial.",
            },
            "months": [{"month": "2026-10-01", "avg_temperature_2m": 27.3}],
        }
        fetch_payload.return_value = payload

        response = self.client.get("/api/weather/monthly")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)
        self.assertEqual(response.headers["cache-control"], "no-store")

    def test_monthly_endpoint_rejects_browser_origins_not_in_allowlist(self) -> None:
        response = self.client.options(
            "/api/weather/monthly",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )

        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_github_pages_origin_is_allowed(self) -> None:
        response = self.client.get(
            "/health",
            headers={"Origin": "https://vaner0.github.io"},
        )

        self.assertEqual(
            response.headers["access-control-allow-origin"],
            "https://vaner0.github.io",
        )

    @patch.dict(os.environ, {"DATABASE_URL": ""})
    def test_database_configuration_error_is_reported_as_service_unavailable(self) -> None:
        from api.main import fetch_monthly_weather_payload
        from fastapi import HTTPException

        with self.assertRaises(HTTPException) as error:
            fetch_monthly_weather_payload()

        self.assertEqual(error.exception.status_code, 503)
        self.assertNotIn("DATABASE_URL", error.exception.detail)


if __name__ == "__main__":
    unittest.main()
