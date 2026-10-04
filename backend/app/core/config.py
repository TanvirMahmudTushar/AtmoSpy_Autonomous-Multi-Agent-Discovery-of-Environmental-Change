from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env.

    No secret ever has a hardcoded default other than empty string; missing
    GROQ_API_KEY degrades the LLM layer to deterministic fallbacks instead of
    failing, per the product requirement that the app works before a key is
    supplied.
    """

    # Looks for .env in the current working directory first, then the repo
    # root, so it resolves whether commands are run from backend/ or root.
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    APP_NAME: str = "AtmoSpy"
    ENV: str = "development"
    API_PREFIX: str = "/api"
    CORS_ORIGINS: str = "http://localhost:3000"
    # Optional regex for origins that can't be listed up front — chiefly
    # Vercel preview deployments, whose URL changes on every push (e.g.
    # `https://atmospy-.*-myteam\.vercel\.app`). Matched in addition to
    # CORS_ORIGINS, never instead of it.
    CORS_ORIGIN_REGEX: str = ""

    DATABASE_URL: str = (
        "postgresql+asyncpg://trend_detective:trend_detective@localhost:55432/trend_detective"
    )

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    # Auth. JWT_SECRET has no safe default in production — the app will
    # still boot with the dev fallback below (so local setup stays
    # zero-config), but you must override it before deploying anywhere
    # real, since anyone with the default could forge tokens.
    JWT_SECRET: str = "dev-only-insecure-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 14  # 14 days

    NASA_POWER_BASE_URL: str = "https://power.larc.nasa.gov/api"
    NASA_POWER_MAX_CONCURRENCY: int = 4
    NASA_POWER_CACHE_TTL_HOURS: int = 24

    # A NASA Earthdata Login bearer token (generated from the user's Earthdata
    # profile page, not a username/password) — the only thing that flips
    # GRACE_FO from a "requires_credentials" stub to a real, active adapter.
    # Create one for free from your NASA Earthdata Login profile page.
    NASA_EARTHDATA_TOKEN: str = ""

    # Safety cap on regional bounding-box queries. NASA POWER's regional
    # endpoint itself hard-rejects (HTTP 422) any request spanning more than
    # 10 degrees in latitude or longitude — this must match that real limit
    # exactly, not just be "some safe-sounding number", or spatial analysis
    # silently fails for any region near the cap.
    MAX_REGION_SPAN_DEGREES: float = 10.0
    MAX_SPATIAL_GRID_CELLS: int = 200

    DISCOVERY_MAX_CONCURRENCY: int = 4

    # In-process scheduler for Watch mode (in-process rather than Celery/cron
    # at this scale).
    # How often the scheduler wakes up and checks for due watches, and how
    # many watch checks can run concurrently when several come due at once.
    WATCH_SCHEDULER_INTERVAL_SECONDS: int = 3600
    WATCH_MAX_CONCURRENCY: int = 2

    @field_validator("DATABASE_URL")
    @classmethod
    def _to_asyncpg_url(cls, url: str) -> str:
        """Accept the connection string exactly as a host hands it out.

        Supabase (and Render Postgres, Heroku, ...) give `postgresql://` or
        `postgres://` URLs, but the app needs the `postgresql+asyncpg://`
        driver form, and asyncpg takes `ssl=` where libpq-style URLs say
        `sslmode=`. Normalising here means the same string can be pasted
        into DATABASE_URL unedited, for both the app and Alembic.
        """
        parts = urlsplit(url)
        scheme = parts.scheme
        if scheme in ("postgres", "postgresql"):
            scheme = "postgresql+asyncpg"
        query = [("ssl" if k == "sslmode" else k, v) for k, v in parse_qsl(parts.query)]
        return urlunsplit((scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
