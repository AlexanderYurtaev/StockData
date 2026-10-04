from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения. Все переменные окружения имеют префикс FP_."""

    model_config = SettingsConfigDict(env_prefix="FP_", env_file=".env", extra="ignore")

    app_name: str = "Позиции участников по фьючерсам на акции — API"
    version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # auto | moex | demo: auto — сначала MOEX, при недоступности демо-данные
    data_source: str = "auto"

    request_timeout: float = 12.0
    fetch_concurrency: int = 8

    instruments_cache_ttl: int = 24 * 3600
    snapshot_cache_ttl: int = 30 * 60
    history_cache_ttl: int = 12 * 3600
    provider_fail_cooldown: int = 120

    history_days_default: int = 14
    history_days_max: int = 1825  # 5 лет
    default_limit: int = 50
    max_limit: int = 500

    # Локальный архив позиций (SQLite): история накапливается и читается из базы
    db_enabled: bool = True
    db_path: str = "data/positions.db"
    # Период фоновой синхронизации срезa позиций, сек (0 — выключить)
    sync_interval: int = 900
    # Сколько последних торговых дней агрегатов держать наготове
    # (докачивается фоном при старте и в цикле синхронизации)
    total_backfill_days: int = 30

    # Внутренний API страницы MOEX «Открытые позиции»
    # (тот же, что использует https://www.moex.com/ru/derivatives/open-positions)
    moex_base_url: str = "https://web.moex.com/moex-web-iss-api/api/v1"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
