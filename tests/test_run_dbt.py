from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from scripts.run_dbt import configure_dbt_environment


class ConfigureDbtEnvironmentTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    @patch("scripts.run_dbt.load_dotenv")
    def test_parses_local_database_url_without_forcing_ssl(self, load_dotenv: object) -> None:
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://postgres:p%40ss@localhost:5433/etl_pipeline"},
            clear=True,
        ):
            configure_dbt_environment()

            self.assertEqual(os.environ["DBT_HOST"], "localhost")
            self.assertEqual(os.environ["DBT_USER"], "postgres")
            self.assertEqual(os.environ["DBT_PASSWORD"], "p@ss")
            self.assertEqual(os.environ["DBT_PORT"], "5433")
            self.assertEqual(os.environ["DBT_DATABASE"], "etl_pipeline")
            self.assertEqual(os.environ["DBT_SSLMODE"], "prefer")

        load_dotenv.assert_called_once()

    @patch("scripts.run_dbt.load_dotenv")
    def test_uses_required_ssl_for_neon(self, _load_dotenv: object) -> None:
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:password@ep-example.neon.tech/weather"},
            clear=True,
        ):
            configure_dbt_environment()

            self.assertEqual(os.environ["DBT_SSLMODE"], "require")

    @patch("scripts.run_dbt.load_dotenv")
    def test_preserves_explicit_sslmode(self, _load_dotenv: object) -> None:
        with patch.dict(
            os.environ,
            {"DATABASE_URL": "postgresql://user:password@localhost/weather?sslmode=disable"},
            clear=True,
        ):
            configure_dbt_environment()

            self.assertEqual(os.environ["DBT_SSLMODE"], "disable")

    @patch("scripts.run_dbt.load_dotenv")
    def test_rejects_unsupported_url_scheme(self, _load_dotenv: object) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "mysql://user:password@localhost/weather"}, clear=True):
            with self.assertRaisesRegex(ValueError, "protocole postgres"):
                configure_dbt_environment()

    @patch("scripts.run_dbt.load_dotenv")
    def test_does_not_include_credentials_in_validation_errors(self, _load_dotenv: object) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:password@localhost"}, clear=True):
            with self.assertRaises(ValueError) as raised:
                configure_dbt_environment()

        self.assertNotIn("password", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
