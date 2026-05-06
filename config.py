from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # LLM Provider: "bedrock" or "anthropic"
    llm_provider: str = "bedrock"

    # Anthropic direct (if using anthropic provider)
    anthropic_api_key: str = ""

    # AWS Bedrock (if using bedrock provider)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-sonnet-4-20250514-v1:0"
    bedrock_model_id_haiku: str = "anthropic.claude-haiku-4-5-20251001-v1:0"

    # Other APIs
    voyage_api_key: str = ""
    cohere_api_key: str = ""

    # Database
    database_url: str = "postgresql://mycukai:mycukai_pass@localhost:5432/mycukai_db"
    redis_url: str = "redis://localhost:6379/0"

    # Telegram
    telegram_bot_token: str = ""

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    environment: str = "development"
    max_queries_per_hour: int = 30
    sentry_dsn: Optional[str] = None
    admin_secret_key: str = "change-this-in-production"
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
