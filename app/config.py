import os
from functools import lru_cache

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

    @property
    def mistral_configured(self) -> bool:
        return bool(self.mistral_api_key.strip())

    @property
    def serpapi_configured(self) -> bool:
        return bool(self.serpapi_key.strip())


@lru_cache
def get_settings() -> Settings:
    apply_streamlit_secrets()
    return Settings()
