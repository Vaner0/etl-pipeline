from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from scripts.export_portfolio_data import MART_COLUMNS, build_portfolio_payload


class BuildPortfolioPayloadTests(unittest.TestCase):
    def test_serializes_monthly_mart_values_without_database_metadata(self) -> None:
        row = (
            date(2026, 10, 1),
            27.3666666667,
            25.7,
            30.5,
            75.2083333333,
            Decimal("1.6"),
            1,
            Decimal("5"),
            Decimal("24"),
        )

        payload = build_portfolio_payload(
            list(MART_COLUMNS),
            [row],
            "dbt_marts",
            datetime(2026, 10, 4, 12, tzinfo=timezone.utc),
        )

        self.assertEqual(payload["metadata"]["source"], "dbt_marts.mart_weather_cotonou_monthly")
        self.assertEqual(payload["metadata"]["generated_at"], "2026-10-04T12:00:00+00:00")
        self.assertEqual(payload["months"][0]["month"], "2026-10-01")
        self.assertEqual(payload["months"][0]["avg_temperature_2m"], 27.3666666667)
        self.assertEqual(payload["months"][0]["rainy_hours"], 5)
        self.assertEqual(payload["months"][0]["observation_count"], 24)
        self.assertNotIn("database_url", payload)

    def test_rejects_missing_columns_or_empty_marts(self) -> None:
        with self.assertRaisesRegex(ValueError, "Colonnes absentes"):
            build_portfolio_payload(["month"], [], "dbt_marts")

        with self.assertRaisesRegex(ValueError, "aucune ligne"):
            build_portfolio_payload(list(MART_COLUMNS), [], "dbt_marts")

    def test_requires_timezone_aware_generation_time(self) -> None:
        row = (
            date(2026, 10, 1),
            27.3,
            25.7,
            30.5,
            75.2,
            1.6,
            1,
            5,
            24,
        )
        with self.assertRaisesRegex(ValueError, "fuseau horaire"):
            build_portfolio_payload(
                list(MART_COLUMNS),
                [row],
                "dbt_marts",
                datetime(2026, 10, 4, 12),
            )


if __name__ == "__main__":
    unittest.main()
