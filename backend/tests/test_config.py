"""DATABASE_URL is accepted in whatever shape a host hands it out (Supabase,
Render, Heroku give `postgresql://` / `postgres://`, libpq-style `sslmode`),
and normalised to what SQLAlchemy's asyncpg driver needs."""

import pytest

from app.core.config import Settings


def _normalised(url: str) -> str:
    return Settings(DATABASE_URL=url).DATABASE_URL


@pytest.mark.parametrize("scheme", ["postgresql", "postgres"])
def test_plain_postgres_scheme_gets_the_asyncpg_driver(scheme):
    url = _normalised(f"{scheme}://postgres.abcdef:pw@aws-0-eu.pooler.supabase.com:5432/postgres")
    assert url == "postgresql+asyncpg://postgres.abcdef:pw@aws-0-eu.pooler.supabase.com:5432/postgres"


def test_already_asyncpg_url_is_untouched():
    url = "postgresql+asyncpg://trend_detective:trend_detective@localhost:55432/trend_detective"
    assert _normalised(url) == url


def test_libpq_sslmode_becomes_asyncpgs_ssl_parameter():
    url = _normalised("postgresql://u:p@db.example.com:5432/postgres?sslmode=require")
    assert url == "postgresql+asyncpg://u:p@db.example.com:5432/postgres?ssl=require"


def test_percent_encoded_password_survives():
    url = _normalised("postgresql://u:p%40ss%2Fword@db.example.com:5432/postgres")
    assert url == "postgresql+asyncpg://u:p%40ss%2Fword@db.example.com:5432/postgres"


def test_cors_regex_defaults_to_off():
    assert Settings().CORS_ORIGIN_REGEX == ""
