"""Centralized configuration for TruthLens AI."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_env: str = Field(default="development", alias="APP_ENV")
    database_url: str = Field(default="sqlite:///./truthlens.db", alias="DATABASE_URL")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")

    # Model
    model_dir: Path = Field(default=Path("./models"), alias="MODEL_DIR")
    tfidf_model_version: str = Field(default="1.0.0", alias="TFIDF_MODEL_VERSION")

    # GDELT Evidence Retrieval
    gdelt_enabled: bool = Field(default=True, alias="GDELT_ENABLED")
    gdelt_timeout_seconds: float = Field(default=10.0, alias="GDELT_TIMEOUT_SECONDS")
    gdelt_max_results: int = Field(default=10, alias="GDELT_MAX_RESULTS")
    gdelt_time_window_days: int = Field(default=7, alias="GDELT_TIME_WINDOW_DAYS")

    # Google Fact Check Tools API
    google_factcheck_enabled: bool = Field(default=False, alias="GOOGLE_FACTCHECK_ENABLED")
    google_factcheck_api_key: Optional[str] = Field(default=None, alias="GOOGLE_FACTCHECK_API_KEY")
    google_factcheck_max_results: int = Field(default=10, alias="GOOGLE_FACTCHECK_MAX_RESULTS")
    google_factcheck_language_codes: str = Field(default="en,hi,te,ta,kn,ml,mr,bn,gu,pa,or,ur", alias="GOOGLE_FACTCHECK_LANGUAGE_CODES")

    # Social Platform Connectors
    x_api_enabled: bool = Field(default=False, alias="X_API_ENABLED")
    x_bearer_token: Optional[str] = Field(default=None, alias="X_BEARER_TOKEN")
    x_api_max_results: int = Field(default=10, alias="X_API_MAX_RESULTS")

    meta_facebook_enabled: bool = Field(default=False, alias="META_FACEBOOK_ENABLED")
    meta_access_token: Optional[str] = Field(default=None, alias="META_ACCESS_TOKEN")
    meta_app_secret: Optional[str] = Field(default=None, alias="META_APP_SECRET")

    whatsapp_enabled: bool = Field(default=False, alias="WHATSAPP_ENABLED")
    whatsapp_access_token: Optional[str] = Field(default=None, alias="WHATSAPP_ACCESS_TOKEN")
    whatsapp_verify_token: Optional[str] = Field(default=None, alias="WHATSAPP_VERIFY_TOKEN")
    whatsapp_app_secret: Optional[str] = Field(default=None, alias="WHATSAPP_APP_SECRET")
    whatsapp_phone_number_id: Optional[str] = Field(default=None, alias="WHATSAPP_PHONE_NUMBER_ID")

    # OCR Settings
    tesseract_enabled: bool = Field(default=False, alias="TESSERACT_ENABLED")
    tesseract_cmd: str = Field(default=r"C:\Program Files\Tesseract-OCR\tesseract.exe", alias="TESSERACT_CMD")
    tesseract_languages: str = Field(default="eng", alias="TESSERACT_LANGUAGES")
    tesseract_dpi: int = Field(default=300, alias="TESSERACT_DPI")
    tesseract_preprocess: bool = Field(default=True, alias="TESSERACT_PREPROCESS")

    google_vision_enabled: bool = Field(default=False, alias="GOOGLE_VISION_ENABLED")
    google_application_credentials: Optional[str] = Field(default=None, alias="GOOGLE_APPLICATION_CREDENTIALS")

    # Translation - Argos
    argos_enabled: bool = Field(default=False, alias="ARGOS_ENABLED")
    argos_pivot_language: str = Field(default="en", alias="ARGOS_PIVOT_LANGUAGE")
    argos_auto_download: bool = Field(default=False, alias="ARGOS_AUTO_DOWNLOAD")

    # Translation - IndicTrans2
    indic_trans2_enabled: bool = Field(default=False, alias="INDIC_TRANS2_ENABLED")
    indic_trans2_model_dir: Path = Field(default=Path("./models/indictrans2"), alias="INDIC_TRANS2_MODEL_DIR")
    indic_trans2_device: str = Field(default="cpu", alias="INDIC_TRANS2_DEVICE")

    # News API
    newsapi_enabled: bool = Field(default=False, alias="NEWSAPI_ENABLED")
    newsapi_key: Optional[str] = Field(default=None, alias="NEWSAPI_KEY")

    # Input Processing Limits
    input_timeout_seconds: float = Field(default=15.0, alias="INPUT_TIMEOUT_SECONDS")
    input_max_length: int = Field(default=100000, alias="INPUT_MAX_LENGTH")
    input_max_response_bytes: int = Field(default=5000000, alias="INPUT_MAX_RESPONSE_BYTES")
    input_max_upload_bytes: int = Field(default=10000000, alias="INPUT_MAX_UPLOAD_BYTES")
    input_max_image_pixels: int = Field(default=25000000, alias="INPUT_MAX_IMAGE_PIXELS")
    input_max_redirects: int = Field(default=5, alias="INPUT_MAX_REDIRECTS")
    input_user_agent: str = Field(default="TruthLensAI/1.0 (news analysis; +https://github.com/truthlens)", alias="INPUT_USER_AGENT")

    # CORS
    cors_origins: str | list[str] = Field(default="http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:4173,http://127.0.0.1:3000", alias="CORS_ORIGINS")

    # Scheduler
    scheduler_enabled: bool = Field(default=False, alias="SCHEDULER_ENABLED")
    scheduler_timezone: str = Field(default="UTC", alias="SCHEDULER_TIMEZONE")
    scheduler_max_instances: int = Field(default=3, alias="SCHEDULER_MAX_INSTANCES")

    # Rate Limiting
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_requests_per_minute: int = Field(default=60, alias="RATE_LIMIT_REQUESTS_PER_MINUTE")
    rate_limit_burst: int = Field(default=10, alias="RATE_LIMIT_BURST")

    @field_validator("model_dir", "indic_trans2_model_dir", mode="before")
    @classmethod
    def _expand_path(cls, v: Any) -> Path:
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return self._parse_cors_origins(self.cors_origins)

    @property
    def tesseract_language_list(self) -> list[str]:
        return [lang.strip() for lang in self.tesseract_languages.split(",") if lang.strip()]

    @property
    def google_factcheck_language_list(self) -> list[str]:
        return [lang.strip() for lang in self.google_factcheck_language_codes.split(",") if lang.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()