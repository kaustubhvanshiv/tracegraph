"""Application configuration loaded exclusively from environment variables.

No secrets have hardcoded defaults — they must be supplied via environment
or a .env file. See .env.example at the repository root for the full list.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
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
    neo4j_uri: str = "bolt://localhost:7687"
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
    llm_api_key: str  # no default — must come from env
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
