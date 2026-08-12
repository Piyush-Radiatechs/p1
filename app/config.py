from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    return Settings()
