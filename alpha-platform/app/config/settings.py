"""
Centralized configuration — flat pydantic-settings model.
All settings are flat with prefixed env var names to avoid
pydantic-settings nested BaseSettings parsing issues.

Usage:
    from app.config.settings import settings
    print(settings.database.url)
    print(settings.telegram.enabled)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://alpha:alpha@localhost:5432/alpha_platform",
        alias="DATABASE_URL",
    )
    database_pool_size: int = Field(default=10)
    database_echo: bool = Field(default=False)

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # Telegram
    telegram_enabled: bool = Field(default=False, alias="TELEGRAM_ENABLED")
    telegram_bot_token: Optional[SecretStr] = Field(default=None, alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: Optional[str] = Field(default=None, alias="TELEGRAM_CHAT_ID")

    # AI
    ai_provider: str = Field(default="anthropic", alias="AI_PROVIDER")
    ai_api_key: Optional[SecretStr] = Field(default=None, alias="AI_API_KEY")
    ai_model: str = Field(default="claude-sonnet-4-5", alias="AI_MODEL")
    ai_reports_enabled: bool = Field(default=False, alias="AI_REPORTS_ENABLED")

    # Research
    research_data_dir: str = Field(default="data/historical", alias="RESEARCH_DATA_DIR")
    research_results_dir: str = Field(default="data/results", alias="RESEARCH_RESULTS_DIR")
    research_commission_pct: float = Field(default=0.001)
    research_slippage_pct: float = Field(default=0.0005)
    research_in_sample_ratio: float = Field(default=0.70)
    research_walk_forward_windows: int = Field(default=5)
    research_min_trades: int = Field(default=30)

    # Paper engine
    paper_initial_equity: float = Field(default=10000.0, alias="PAPER_INITIAL_EQUITY")
    paper_state_file: str = Field(
        default="data/state/paper_engine_state.json",
        alias="PAPER_STATE_FILE",
    )

    # API
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_debug: bool = Field(default=False, alias="API_DEBUG")
    api_secret_key: str = Field(default="change-me-in-production", alias="API_SECRET_KEY")

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
        extra="ignore",
    )

    @property
    def env(self) -> str:
        return self.app_env

    # Namespace shims so callers can use settings.research.data_dir style
    @property
    def research(self):
        s = self
        class _R:
            data_dir = s.research_data_dir
            results_dir = s.research_results_dir
            commission_pct = s.research_commission_pct
            slippage_pct = s.research_slippage_pct
            in_sample_ratio = s.research_in_sample_ratio
            walk_forward_windows = s.research_walk_forward_windows
            min_trades = s.research_min_trades
        return _R()

    @property
    def paper_engine(self):
        s = self
        class _P:
            initial_equity = s.paper_initial_equity
            state_file = s.paper_state_file
        return _P()

    @property
    def telegram(self):
        s = self
        class _T:
            enabled = s.telegram_enabled
            bot_token = s.telegram_bot_token
            chat_id = s.telegram_chat_id
        return _T()

    @property
    def ai(self):
        s = self
        class _A:
            enabled = s.ai_reports_enabled
            api_key = s.ai_api_key
            model = s.ai_model
            provider = s.ai_provider
        return _A()

    @property
    def api(self):
        s = self
        class _API:
            host = s.api_host
            port = s.api_port
            debug = s.api_debug
        return _API()

    @property
    def database(self):
        s = self
        class _DB:
            url = s.database_url
            pool_size = s.database_pool_size
            echo = s.database_echo
        return _DB()

    @classmethod
    def from_yaml(cls, yaml_path=None) -> "Settings":
        if yaml_path is None:
            yaml_path = ROOT_DIR / "config" / "settings.yaml"
        if Path(yaml_path).exists():
            with open(yaml_path) as f:
                data = yaml.safe_load(f) or {}
            for key, val in _flatten(data).items():
                if key.upper() not in os.environ:
                    os.environ[key.upper()] = str(val)
        return cls()


def _flatten(d: dict, prefix: str = "") -> dict:
    items = {}
    for k, v in d.items():
        full = f"{prefix}_{k}".strip("_") if prefix else k
        if isinstance(v, dict):
            items.update(_flatten(v, full))
        else:
            items[full] = v
    return items


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_yaml()


settings = get_settings()
