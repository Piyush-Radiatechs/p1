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
