"""Centralized application settings using Pydantic Settings."""

from pathlib import Path
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """PodcastPulse AI application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application metadata
    app_env: str = Field(default="development", description="Application environment (development, test, production)")
    app_version: str = Field(default="0.1.0", description="Application version")

    # Database URLs (MySQL 8 via PyMySQL - override via .env)
    database_url: str = Field(
        default="mysql+pymysql://podcastpulse_user:password@localhost:3306/podcastpulse_db",
        description="Primary relational database connection string",
    )
    test_database_url: str = Field(
        default="mysql+pymysql://podcastpulse_test_user:password@localhost:3306/podcastpulse_test",
        description="Integration test relational database connection string",
    )
    database_echo: bool = Field(default=False, description="Enable SQLAlchemy SQL query echo")

    # Server configuration
    api_host: str = Field(default="127.0.0.1", description="FastAPI bind host")
    api_port: int = Field(default=8000, description="FastAPI bind port")
    streamlit_port: int = Field(default=8501, description="Streamlit dashboard port")
    cors_allowed_origins: List[str] = Field(
        default=["http://localhost:8501", "http://127.0.0.1:8501"],
        description="Allowed CORS origins (explicit list, never wildcard)",
    )

    # Local storage & paths
    data_dir: Path = Field(default=Path("./data"), description="Base directory for local file storage")

    # External tooling paths & API Keys (Phase 2)
    ffmpeg_path: str = Field(default="ffmpeg", description="Path or command for FFmpeg executable")
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama API base URL")
    youtube_api_key: str | None = Field(default=None, description="YouTube Data API v3 key")
    discovery_max_results: int = Field(default=25, description="Default max results per YouTube search query")
    discovery_max_queries_per_run: int = Field(default=5, description="Max queries executed per discovery run")

    # Logging & Observability
    log_level: str = Field(default="INFO", description="Standard logging level")
    log_format: str = Field(default="json", description="Log format: json or console")

    # Job Settings
    job_default_max_retries: int = Field(default=3, description="Default max retries for transient failures")
    job_lock_timeout_seconds: int = Field(default=300, description="Job execution lock timeout")

    @field_validator("data_dir", mode="after")
    @classmethod
    def validate_data_dir(cls, v: Path) -> Path:
        """Resolve and ensure data_dir path is safe."""
        resolved = v.resolve()
        return resolved


# Singleton settings instance
settings = Settings()
