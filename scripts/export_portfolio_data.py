"""Export the dbt monthly mart to a static, credential-free portfolio snapshot."""

from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg import sql

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MART_TABLE = "mart_weather_cotonou_monthly"
MART_COLUMNS = (
    "month",
    "avg_temperature_2m",
    "min_temperature_2m",
    "max_temperature_2m",
    "avg_relative_humidity_2m",
    "total_precipitation",
    "rainy_days",
    "rainy_hours",
    "observation_count",
)
DEFAULT_OUTPUT = PROJECT_ROOT / "site" / "data" / "weather-monthly.json"


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (Decimal, int, float)) and not isinstance(value, bool):
        return float(value)
    raise ValueError(f"Valeur numérique invalide dans le mart : {value!r}")


def build_portfolio_payload(
    columns: list[str],
    rows: list[tuple[Any, ...]],
    source_schema: str,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Convert database rows into the public JSON contract used by the dashboard."""
    missing_columns = [column for column in MART_COLUMNS if column not in columns]
    if missing_columns:
        raise ValueError(f"Colonnes absentes du mart dbt : {', '.join(missing_columns)}")
    if not rows:
        raise ValueError("Le mart dbt ne contient aucune ligne à publier.")

    column_indexes = {column: columns.index(column) for column in MART_COLUMNS}
    months: list[dict[str, Any]] = []
    for row in rows:
        month_value = row[column_indexes["month"]]
        if not isinstance(month_value, date):
            raise ValueError("La colonne 'month' du mart doit être une date.")
        months.append(
            {
                "month": month_value.isoformat(),
                "avg_temperature_2m": _as_float(row[column_indexes["avg_temperature_2m"]]),
                "min_temperature_2m": _as_float(row[column_indexes["min_temperature_2m"]]),
                "max_temperature_2m": _as_float(row[column_indexes["max_temperature_2m"]]),
                "avg_relative_humidity_2m": _as_float(
                    row[column_indexes["avg_relative_humidity_2m"]]
                ),
                "total_precipitation": _as_float(row[column_indexes["total_precipitation"]]),
                "rainy_days": int(row[column_indexes["rainy_days"]]),
                "rainy_hours": int(row[column_indexes["rainy_hours"]]),
                "observation_count": int(row[column_indexes["observation_count"]]),
            }
        )

    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("generated_at doit inclure un fuseau horaire.")

    return {
        "metadata": {
            "generated_at": timestamp.astimezone(timezone.utc).isoformat(),
            "source": f"{source_schema}.{MART_TABLE}",
            "dataset": "Open-Meteo Archive API — Cotonou, Bénin",
            "note": (
                "Les agrégats mensuels sont partiels : ils ne couvrent que les journées "
                "présentes dans la table source au moment de l'export."
            ),
        },
        "months": months,
    }


def export_portfolio_data(output_path: Path) -> int:
    """Read the dbt mart and atomically write its public, non-sensitive snapshot."""
    load_dotenv(PROJECT_ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL est absent; configurez-le dans le fichier .env.")

    with psycopg.connect(database_url, connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT table_schema
                FROM information_schema.tables
                WHERE table_name = %s
                  AND table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                """,
                (MART_TABLE,),
            )
            schemas = [row[0] for row in cursor.fetchall()]
            if len(schemas) != 1:
                raise RuntimeError(
                    f"Le mart {MART_TABLE} doit exister dans un seul schéma "
                    f"(trouvé : {len(schemas)})."
                )

            source_schema = schemas[0]
            query = sql.SQL("SELECT {} FROM {}.{} ORDER BY {}").format(
                sql.SQL(", ").join(map(sql.Identifier, MART_COLUMNS)),
                sql.Identifier(source_schema),
                sql.Identifier(MART_TABLE),
                sql.Identifier("month"),
            )
            cursor.execute(query)
            columns = [description.name for description in cursor.description or ()]
            rows = cursor.fetchall()

    payload = build_portfolio_payload(columns, rows, source_schema)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Fichier JSON à générer (par défaut : {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    row_count = export_portfolio_data(args.output)
    print(f"Export du mart terminé : {row_count} mois publiés dans {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
