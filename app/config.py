from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
import json

class Settings(BaseSettings):
    project_name: str = Field(default="KVT Service Bot", alias="PROJECT_NAME")
    env: str = Field(default="development", alias="ENV")
    tz: str = Field(default="UTC", alias="TZ")

    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="kvtservice", alias="POSTGRES_DB")
    postgres_user: str = Field(default="kvt", alias="POSTGRES_USER")
    postgres_password: str = Field(default="kvtpassword", alias="POSTGRES_PASSWORD")

    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="admin123", alias="ADMIN_PASSWORD")

    bot_token: str = Field(default="", alias="BOT_TOKEN")
    admin_telegram_chat_id: int = Field(default=0, alias="ADMIN_TELEGRAM_CHAT_ID")

    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=465, alias="SMTP_PORT")
    smtp_user: str | None = Field(default="sbcargobot@gmail.com", alias="SMTP_USER")
    smtp_password: str | None = Field(default="1Qqazxsw55", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="sbcargobot@gmail.com", alias="SMTP_FROM")

    default_notification_email: str = Field(default="sb@sbcargo.ru", alias="DEFAULT_NOTIFICATION_EMAIL")
    email_enabled: bool = Field(default=True, alias="EMAIL_ENABLED")

    # Read as raw string to avoid DotEnv JSON parsing for complex types
    cors_origins_raw: str = Field(default="*", alias="CORS_ORIGINS")

    @property
    def cors_origins(self) -> List[str]:
        raw = (self.cors_origins_raw or "").strip()
        if not raw:
            return ["*"]
        if raw in {"*", "'*'", '"*"'}:
            return ["*"]
        # Try JSON array first
        if raw.startswith("["):
            try:
                data = json.loads(raw)
                return [str(item).strip() for item in data if str(item).strip()]
            except Exception:
                pass
        # Fallback: comma-separated
        return [part.strip() for part in raw.split(",") if part.strip()]

    class Config:
        env_file = "local.env"
        case_sensitive = False

settings = Settings()
