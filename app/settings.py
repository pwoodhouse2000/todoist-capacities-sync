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
    gcp_project_id: str = "notion-todoist-sync-464419"
    firestore_namespace: str = "todoist-notion-v1"
    default_timezone: str = "America/Los_Angeles"

    # Pub/Sub Configuration
    pubsub_topic: str = "todoist-sync-jobs"
    pubsub_subscription: str = "todoist-sync-worker"

    # Logging
    log_level: str = "INFO"

    # API Tokens (from Secret Manager in production, env vars in dev)
    todoist_oauth_token: str
    notion_api_key: str
    internal_cron_token: str = "dev-token-change-in-production"

    # Notion Configuration
    notion_tasks_database_id: str
    notion_projects_database_id: str
    notion_areas_database_id: str = ""  # Optional: AREAS database for PARA method
    notion_people_database_id: str = ""  # Optional: People database for person assignments

    # API Base URLs
    todoist_api_base_url: str = "https://api.todoist.com/rest/v2"
    notion_api_base_url: str = "https://api.notion.com/v1"

    # Rate limiting and retries
    max_retries: int = 3
    retry_delay: float = 1.0
    request_timeout: int = 30

    # Feature flags
    add_notion_backlink: bool = True  # Add Notion page link to Todoist task description
    enable_para_areas: bool = True  # Enable PARA method area mapping
    enable_people_matching: bool = True  # Enable automatic people matching from labels
    auto_label_tasks: bool = True  # Auto-add capsync label to eligible tasks (not in Inbox, not recurring)
    
    # PARA Method Configuration
    para_area_labels: list[str] = [
        "HOME", "HEALTH", "PROSPER", "WORK", 
        "PERSONAL & FAMILY", "FINANCIAL", "FUN"
    ]
    
    # People matching configuration
    person_label_emoji: str = "👤"  # Emoji that identifies a person label


# Global settings instance
settings = Settings()

