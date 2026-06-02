import json
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    project_name: str = Field(default="KVT Service Bot", alias="PROJECT_NAME")
    env: str = Field(default="development", alias="ENV")
    tz: str = Field(default="UTC", alias="TZ")

    database_url: str | None = Field(default=None, alias="DATABASE_URL")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="kvtservice", alias="POSTGRES_DB")
    postgres_user: str = Field(default="kvt", alias="POSTGRES_USER")
    postgres_password: str = Field(default="", alias="POSTGRES_PASSWORD")

    admin_username: str = Field(default="admin", alias="ADMIN_USERNAME")
    admin_password: str = Field(default="", alias="ADMIN_PASSWORD")

    bot_token: str = Field(default="", alias="BOT_TOKEN")
    admin_max_chat_id: int = Field(default=0, alias="ADMIN_MAX_CHAT_ID")
    admin_telegram_chat_id: int = Field(default=0, alias="ADMIN_TELEGRAM_CHAT_ID")

    smtp_host: str = Field(default="smtp.gmail.com", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str | None = Field(default=None, alias="SMTP_USER")
    smtp_password: str | None = Field(default=None, alias="SMTP_PASSWORD")
    gmail_app_password: str | None = Field(default=None, alias="GMAIL_APP_PASSWORD")
    smtp_from: str | None = Field(default=None, alias="SMTP_FROM")

    default_notification_email: str | None = Field(default=None, alias="DEFAULT_NOTIFICATION_EMAIL")
    email_enabled: bool = Field(default=True, alias="EMAIL_ENABLED")
    startup_email_test: bool = Field(default=False, alias="STARTUP_EMAIL_TEST")
    resend_api_key: str | None = Field(default=None, alias="RESEND_API_KEY")

    bitrix24_webhook: str | None = Field(default=None, alias="BITRIX24_WEBHOOK")
    max_chat_url: str | None = Field(default=None, alias="MAX_CHAT_URL")

    cors_origins_raw: str = Field(default="*", alias="CORS_ORIGINS")

    @property
    def cors_origins(self) -> List[str]:
        raw = (self.cors_origins_raw or "").strip()
        if not raw:
            return ["*"]
        if raw in {"*", "'*'", '"*"'}:
            return ["*"]
        if raw.startswith("["):
            try:
                data = json.loads(raw)
                return [str(item).strip() for item in data if str(item).strip()]
            except Exception:
                pass
        return [part.strip() for part in raw.split(",") if part.strip()]

    @property
    def admin_chat_id(self) -> int:
        return self.admin_max_chat_id or self.admin_telegram_chat_id

    @property
    def smtp_login_password(self) -> str | None:
        raw = self.gmail_app_password or self.smtp_password
        if raw is None:
            return None
        return raw.replace(" ", "")

    @property
    def resolved_smtp_from(self) -> str:
        return self.smtp_from or self.smtp_user or "noreply@example.com"

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
