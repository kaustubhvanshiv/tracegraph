"""Application configuration loaded exclusively from environment variables.

No secrets have hardcoded defaults — they must be supplied via environment
or a .env file. See .env.example at the repository root for the full list.

The .env file is resolved in this order:
  1. backend/.env        (if running uvicorn from the backend/ directory)
  2. ../.env             (workspace root — the canonical location)
Both are listed so the app works regardless of where uvicorn is launched from.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve paths relative to this file so they work from any working directory
_this_dir = Path(__file__).resolve().parent          # backend/app/core/
_backend_dir = _this_dir.parent.parent               # backend/
_root_dir = _backend_dir.parent                      # workspace root


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # List both locations; pydantic-settings merges them, later entries win
        env_file=(
            str(_backend_dir / ".env"),   # backend/.env  (optional local override)
            str(_root_dir / ".env"),      # workspace root .env  (canonical)
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # PostgreSQL (Supabase connection pooler)
    # ------------------------------------------------------------------
    postgres_host: str = "aws-0-ap-south-1.pooler.supabase.com"
    postgres_port: int = 5432
    postgres_db: str = "postgres"
    postgres_user: str = "postgres.qxrzhmcsxvbsoydeywkr"
    postgres_password: str  # no default — must come from env

    # ------------------------------------------------------------------
    # Neo4j
    # ------------------------------------------------------------------
    neo4j_uri: str = "bolt://localhost:7687"  # override with neo4j+s:// for AuraDB
    neo4j_user: str = "neo4j"
    neo4j_password: str  # no default — must come from env

    # ------------------------------------------------------------------
    # JWT
    # ------------------------------------------------------------------
    jwt_secret_key: str  # no default — must come from env
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------
    llm_provider: str = "openai"
    llm_api_key: str | None = None  # optional — only required when AI summary is used
    llm_model: str = "gpt-4o"
    llm_timeout_seconds: int = 30

    # ------------------------------------------------------------------
    # App
    # ------------------------------------------------------------------
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = ["http://localhost:5173"]

    # ------------------------------------------------------------------
    # Pipeline defaults
    # ------------------------------------------------------------------
    default_window_minutes: int = 10
    max_context_events: int = 50


settings = Settings()
