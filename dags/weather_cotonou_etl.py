"""Manual Airflow demo DAG for the Cotonou weather extraction and dbt build."""

from __future__ import annotations

import os
import subprocess
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.sdk import dag, task

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
EXTRACTION_SCRIPT = PROJECT_ROOT / "extraction" / "extract_weather_cotonou.py"
DBT_RUNNER = PROJECT_ROOT / "scripts" / "run_dbt.py"


@dag(
    dag_id="weather_cotonou_etl",
    description="Extraction Open-Meteo vers PostgreSQL puis transformations dbt.",
    schedule=None,
    start_date=pendulum.datetime(2026, 9, 1, tz="UTC"),
    catchup=False,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["etl", "open-meteo", "postgres", "dbt"],
)
def weather_cotonou_etl():
    @task
    def extract_and_load() -> None:
        if not os.environ.get("DATABASE_URL"):
            raise RuntimeError(
                "DATABASE_URL n'est pas configurée dans les secrets d'environnement du Codespace."
            )
        subprocess.run(
            [str(PROJECT_PYTHON), str(EXTRACTION_SCRIPT)],
            cwd=PROJECT_ROOT,
            check=True,
            env=os.environ.copy(),
        )

    @task
    def transform_with_dbt() -> None:
        if not os.environ.get("DATABASE_URL"):
            raise RuntimeError(
                "DATABASE_URL n'est pas configurée dans les secrets d'environnement du Codespace."
            )
        subprocess.run(
            [str(PROJECT_PYTHON), str(DBT_RUNNER), "build"],
            cwd=PROJECT_ROOT,
            check=True,
            env=os.environ.copy(),
        )

    extract_and_load() >> transform_with_dbt()


weather_cotonou_etl()
