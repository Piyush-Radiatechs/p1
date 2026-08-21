import os

from app.config import apply_streamlit_secrets, get_settings


def test_apply_streamlit_secrets_is_safe_without_streamlit_runtime():
    apply_streamlit_secrets()


def test_get_settings_reads_env(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("MISTRAL_API_KEY", "test-mistral-key")
    settings = get_settings()
    assert settings.mistral_configured
    assert settings.mistral_api_key == "test-mistral-key"
    get_settings.cache_clear()
    os.environ.pop("MISTRAL_API_KEY", None)


def test_postgres_url_is_normalized_for_sqlalchemy(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@ep-example.neon.tech/neondb?sslmode=require",
    )
    settings = get_settings()
    assert settings.sqlalchemy_database_url.startswith("postgresql+psycopg://")
    get_settings.cache_clear()
    os.environ.pop("DATABASE_URL", None)


def test_neon_channel_binding_is_stripped(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@ep-example-pooler.neon.tech/neondb"
        "?sslmode=require&channel_binding=require",
    )
    settings = get_settings()
    url = settings.sqlalchemy_database_url
    assert "channel_binding" not in url
    assert "sslmode=require" in url
    assert url.startswith("postgresql+psycopg://")
    get_settings.cache_clear()
    os.environ.pop("DATABASE_URL", None)
