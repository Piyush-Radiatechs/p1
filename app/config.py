import os
from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic_settings import BaseSettings, SettingsConfigDict

_SECRET_ENV_KEYS = (
    "MISTRAL_API_KEY",
    "MISTRAL_MODEL",
    "SERPAPI_KEY",
    "MAX_QUERIES_PER_JD",
    "MAX_RESULTS_PER_QUERY",
    "GOOGLE_DOMAIN",
    "GOOGLE_GL",
    "GOOGLE_HL",
    "DATABASE_URL",
)


def apply_streamlit_secrets() -> None:
    """Copy Streamlit Cloud secrets into environment variables.

    GitHub Actions secrets are not available to Streamlit Cloud. App secrets
    must be set in the Streamlit Cloud dashboard (Manage app → Settings → Secrets).
    Existing OS / .env values take precedence.
    """
    try:
        import streamlit as st

        secrets = st.secrets
    except Exception:
        return

    for key in _SECRET_ENV_KEYS:
        if os.environ.get(key, "").strip():
            continue
        try:
            value = secrets[key]
        except Exception:
            continue
        if value is None:
            continue
        text = str(value).strip()
        if text:
            os.environ[key] = text


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mistral_api_key: str = ""
    mistral_model: str = "mistral-small-latest"

    serpapi_key: str = ""

    max_queries_per_jd: int = 5
    max_results_per_query: int = 10

    google_domain: str = "google.com"
    google_gl: str = "us"
    google_hl: str = "en"

    # SQLite locally; set to a Neon/Supabase Postgres URL when hosting.
    database_url: str = "sqlite:///./data/app.db"

    @property
    def sqlalchemy_database_url(self) -> str:
        return normalize_database_url(self.database_url)

    @property
    def mistral_configured(self) -> bool:
        return bool(self.mistral_api_key.strip())

    @property
    def serpapi_configured(self) -> bool:
        return bool(self.serpapi_key.strip())


def normalize_database_url(raw_url: str | None) -> str:
    """Prepare DATABASE_URL for SQLAlchemy + Neon/Postgres.

    Neon copies often include channel_binding=require, which can drop the SSL
    handshake with psycopg on Windows. That parameter is stripped here.
    """
    url = (raw_url or "").strip().strip("'").strip('"') or "sqlite:///./data/app.db"
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]

    if url.startswith("sqlite"):
        return url

    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.pop("channel_binding", None)
    if not query.get("sslmode"):
        query["sslmode"] = "require"
    return urlunparse(parsed._replace(query=urlencode(query)))


@lru_cache
def get_settings() -> Settings:
    apply_streamlit_secrets()
    return Settings()
