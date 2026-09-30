"""Load dbt connection settings from DATABASE_URL and run the dbt CLI."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt"
DBT_PROFILES_DIR = PROJECT_ROOT / "dbt"
PROFILE_TEMPLATE = DBT_PROFILES_DIR / "profiles.yml.example"
PROFILE_FILE = DBT_PROFILES_DIR / "profiles.yml"


def configure_dbt_environment() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL est absent; configurez-le dans le fichier .env.")

    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ValueError("DATABASE_URL doit utiliser le protocole postgres:// ou postgresql://.")
    if not parsed.hostname or not parsed.username or not parsed.path.strip("/"):
        raise ValueError("DATABASE_URL doit inclure un hôte, un utilisateur et un nom de base.")

    try:
        port = parsed.port or 5432
    except ValueError as exc:
        raise ValueError("DATABASE_URL contient un port PostgreSQL invalide.") from exc

    query = parse_qs(parsed.query)
    sslmode = query.get("sslmode", ["require" if parsed.hostname.endswith(".neon.tech") else "prefer"])[0]
    os.environ.update(
        {
            "DBT_HOST": parsed.hostname,
            "DBT_USER": unquote(parsed.username),
            "DBT_PASSWORD": unquote(parsed.password or ""),
            "DBT_PORT": str(port),
            "DBT_DATABASE": unquote(parsed.path.lstrip("/")),
            "DBT_SSLMODE": sslmode,
            "DBT_PROFILES_DIR": str(DBT_PROFILES_DIR),
        }
    )


def dbt_executable() -> Path:
    executable_name = "dbt.exe" if os.name == "nt" else "dbt"
    executable = Path(sys.executable).parent / executable_name
    if not executable.is_file():
        raise RuntimeError(f"Exécutable dbt introuvable dans l’environnement Python: {executable}")
    return executable


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_dbt.py <commande dbt> [arguments...]", file=sys.stderr)
        return 2

    try:
        configure_dbt_environment()
        executable = dbt_executable()
        if not PROFILE_FILE.exists():
            shutil.copyfile(PROFILE_TEMPLATE, PROFILE_FILE)
    except (RuntimeError, ValueError) as exc:
        print(f"Configuration dbt invalide: {exc}", file=sys.stderr)
        return 2

    result = subprocess.run(
        [str(executable), *sys.argv[1:]],
        cwd=DBT_PROJECT_DIR,
        check=False,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
