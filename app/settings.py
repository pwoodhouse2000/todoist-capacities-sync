"""Application settings and configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # GCP Configuration
    gcp_project_id: str
    firestore_namespace: str = "todoist-capacities-v1"
    default_timezone: str = "America/Los_Angeles"

    # Pub/Sub Configuration
    pubsub_topic: str = "todoist-sync-jobs"
    pubsub_subscription: str = "todoist-sync-worker"

    # Logging
    log_level: str = "INFO"

    # API Tokens (from Secret Manager in production, env vars in dev)
    todoist_oauth_token: str
    capacities_api_key: str
    internal_cron_token: str

    # Capacities Configuration
    capacities_space_id: str

    # API Base URLs
    todoist_api_base_url: str = "https://api.todoist.com/rest/v2"
    capacities_api_base_url: str = "https://api.capacities.io"

    # Rate limiting and retries
    max_retries: int = 3
    retry_delay: float = 1.0
    request_timeout: int = 30


# Global settings instance
settings = Settings()

