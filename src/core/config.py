import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Aurum"
    debug: bool = False

    # LLM
    llm_provider: str = "anthropic"
    llm_model: str = "claude-opus-4-7"
    llm_max_tokens: int = 4096
    llm_temperature: float = 0.3

    # LLM API keys (all optional — only the active provider's key is required)
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_region: str = "us-east-1"

    # Database
    database_url: str = "postgresql+asyncpg://aurum:aurum_dev@localhost:5432/aurum"
    use_sqlite: bool = False

    # Redis / Cache
    redis_url: str = "redis://localhost:6379/0"
    use_in_memory_cache: bool = False

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8000
    chroma_persist_dir: str = "/data/chroma"

    # Auth
    secret_key: SecretStr = SecretStr("change-me-to-a-secure-random-string")
    access_token_expire_minutes: int = 10080  # 7 days
    algorithm: str = "HS256"

    # External adapters
    alpha_vantage_api_key: SecretStr | None = None
    nasdaq_data_link_api_key: SecretStr | None = None

    # Admin
    admin_emails: str = ""

    # LangSmith observability (optional)
    langchain_tracing_v2: str = "false"
    langchain_api_key: SecretStr | None = None
    langchain_project: str = "aurum"

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]

    @property
    def langsmith_enabled(self) -> bool:
        return self.langchain_tracing_v2.lower() == "true"

    # Cache TTLs (seconds)
    cache_ttl_quote: int = 60
    cache_ttl_history: int = 300
    cache_ttl_index: int = 3600
    cache_ttl_news: int = 900

    # Derived from config.yaml (loaded separately)
    _yaml_config: dict[str, Any] = {}

    @model_validator(mode="after")
    def apply_sqlite_url(self) -> "Settings":
        if self.use_sqlite:
            self.database_url = "sqlite+aiosqlite:///./data/aurum.db"
        return self

    def get_yaml(self) -> dict[str, Any]:
        if not self._yaml_config:
            cfg_path = Path("config.yaml")
            if cfg_path.exists():
                with open(cfg_path) as f:
                    object.__setattr__(self, "_yaml_config", yaml.safe_load(f) or {})
        return self._yaml_config

    @property
    def data_sources_config(self) -> dict:
        return self.get_yaml().get("data_sources", {})

    @property
    def news_sources_config(self) -> dict:
        return self.get_yaml().get("news_sources", {})

    @property
    def guardrails_config(self) -> dict:
        return self.get_yaml().get("guardrails", {})

    @property
    def supervisor_config(self) -> dict:
        return self.get_yaml().get("supervisor", {})

    @property
    def default_indices(self) -> list[str]:
        return self.get_yaml().get("indices", ["^GSPC", "^NDX", "^DJI", "^VIX"])

    @property
    def disclaimer_text(self) -> str:
        return self.guardrails_config.get(
            "disclaimer_text",
            "This is educational information only and does not constitute financial advice.",
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
