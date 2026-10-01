#!/usr/bin/env bash
set -euo pipefail

AIRFLOW_VERSION="3.1.6"
PYTHON_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
CONSTRAINTS_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt

python3 -m venv .venv-airflow
.venv-airflow/bin/python -m pip install \
  "apache-airflow==${AIRFLOW_VERSION}" \
  "apache-airflow-providers-standard" \
  --constraint "${CONSTRAINTS_URL}"

mkdir -p "${AIRFLOW_HOME}"
