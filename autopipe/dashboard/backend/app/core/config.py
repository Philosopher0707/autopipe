"""Application configuration settings."""

import secrets
from typing import Any, List, Optional, Union

from pydantic import field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Project info
    PROJECT_NAME: str = "AutoPipe Dashboard"
    PROJECT_DESCRIPTION: str = "Production-grade ML Pipeline Dashboard"
    VERSION: str = "1.0.0"

    # API settings
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # CORS - dev defaults (override in production via env vars)
    BACKEND_CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000", "http://localhost:5173"])

    # Production CORS origins (split from env string)
    PRODUCTION_CORS_ORIGINS: Optional[str] = None

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Database
    DATABASE_URL: str = "sqlite:///./autopipe_dashboard.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis (for caching and pub/sub)
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_PASSWORD: Optional[str] = None

    # WebSocket
    WS_MESSAGE_QUEUE: str = "redis"  # Options: memory, redis

    # File storage
    UPLOAD_DIR: str = "./uploads"
    ARTIFACTS_DIR: str = "./artifacts"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB

    # Security
    PASSWORD_MIN_LENGTH: int = 8
    JWT_ALGORITHM: str = "HS256"

    # Rate Limiting
    RATE_LIMIT_LOGIN_REQUESTS: int = 5
    RATE_LIMIT_LOGIN_WINDOW: int = 300  # 5 minutes in seconds
    RATE_LIMIT_REGISTER_REQUESTS: int = 3
    RATE_LIMIT_REGISTER_WINDOW: int = 3600  # 1 hour in seconds
    RATE_LIMIT_DEFAULT_REQUESTS: int = 100
    RATE_LIMIT_DEFAULT_WINDOW: int = 60  # 1 minute in seconds

    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Pagination defaults
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100


# Global settings instance
settings = Settings()
