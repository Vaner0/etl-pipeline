from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from psycopg import sql

from scripts.export_portfolio_data import MART_COLUMNS, MART_TABLE, build_portfolio_payload

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)

DEFAULT_CORS_ORIGINS = (
    "https://vaner0.github.io",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
)

app = FastAPI(
    title="Cotonou Weather Data API",
    description="Read-only API exposing the monthly dbt weather mart.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(",")
        if origin.strip()
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Accept"],
)


def fetch_monthly_weather_payload() -> dict[str, Any]:
    """Read and serialize the dbt mart without exposing connection details."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise HTTPException(
            status_code=503,
            detail="The weather database is not configured.",
        )

    try:
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
                        f"Expected one {MART_TABLE} table; found {len(schemas)}."
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

        return build_portfolio_payload(columns, rows, source_schema)
    except (psycopg.Error, RuntimeError, ValueError) as exc:
        logger.error("Monthly weather mart request failed (%s).", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Monthly weather data is temporarily unavailable.",
        ) from exc


@app.get("/health")
def health() -> dict[str, str]:
    """Return service liveness for the hosting platform."""
    return {"status": "ok"}


@app.get("/api/weather/monthly")
def monthly_weather(response: Response) -> dict[str, Any]:
    """Return the monthly dbt mart as the dashboard's public JSON contract."""
    response.headers["Cache-Control"] = "no-store"
    return fetch_monthly_weather_payload()
