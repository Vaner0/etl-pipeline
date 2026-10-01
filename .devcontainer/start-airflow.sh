#!/usr/bin/env bash
set -euo pipefail

AIRFLOW_BIN="${PWD}/.venv-airflow/bin/airflow"
export PATH="${PWD}/.venv-airflow/bin:${PATH}"
if [[ -n "${CODESPACE_NAME:-}" && -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]]; then
  export AIRFLOW__API__BASE_URL="https://${CODESPACE_NAME}-8080.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}"
fi
PID_FILE="/tmp/etl-pipeline-airflow.pid"
LOG_FILE="${AIRFLOW_HOME}/standalone.log"

if [[ ! -x "${AIRFLOW_BIN}" ]]; then
  echo "Airflow n'est pas installé. Relancez la configuration du Codespace."
  exit 1
fi

if [[ -f "${PID_FILE}" ]]; then
  PID="$(cat "${PID_FILE}")"
  if kill -0 "${PID}" 2>/dev/null && ps -p "${PID}" -o args= | grep -Fq "${AIRFLOW_BIN} standalone"; then
    if curl --fail --silent --show-error http://127.0.0.1:8080/api/v2/version >/dev/null 2>&1; then
      echo "Airflow standalone est déjà en cours."
      exit 0
    fi
    echo "Le processus Airflow existe (PID ${PID}), mais l'API ne répond pas sur le port 8080."
    echo "Arrêtez ce processus avec 'kill ${PID}', puis relancez ce script."
    exit 1
  fi
  rm -f "${PID_FILE}"
fi

nohup "${AIRFLOW_BIN}" standalone >"${LOG_FILE}" 2>&1 </dev/null &
echo "$!" >"${PID_FILE}"

for _ in $(seq 1 90); do
  if ! kill -0 "$(cat "${PID_FILE}")" 2>/dev/null; then
    echo "Airflow s'est arrêté pendant son démarrage. Consultez le journal local du Codespace."
    exit 1
  fi
  if curl --fail --silent --show-error http://127.0.0.1:8080/api/v2/version >/dev/null 2>&1; then
    echo "Airflow est disponible sur le port 8080. Les identifiants de démonstration sont dans le journal local du Codespace."
    exit 0
  fi
  sleep 2
done

echo "Airflow n'a pas ouvert le port 8080 à temps. Consultez le journal local du Codespace."
exit 1
