import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    DATABASE_URL: str
    TEST_DATABASE_URL: str
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    HMAC_SECRET: str
    ENCRYPTION_KEY: str
    SEED_PASSWORD: str = ""
    CORS_ORIGINS: List[str] = []
    STORAGE_DIR: str = "./storage"
    VERIFY_BASE_URL: str = ""
    FRONTEND_BASE_URL: str = "http://localhost:5173"
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_SSL: bool = False
    SMTP_STARTTLS: bool = True
    PASSWORD_RESET_EXPIRE_MINUTES: int = 20
    DEMO_ALLOW_UNVERIFIED_PASSWORD_RESET: bool = True

    def __post_init__(self):
        # Ensure required secrets are not empty placeholders
        for secret_name in ("JWT_SECRET_KEY", "HMAC_SECRET", "ENCRYPTION_KEY"):
            if not getattr(self, secret_name):
                raise ValueError(f"{secret_name} must be set and not empty")

    @property
    def password_reset_email_configured(self) -> bool:
        sender = self.EMAIL_FROM or self.SMTP_FROM_EMAIL
        return bool(sender and self.FRONTEND_BASE_URL and (self.RESEND_API_KEY or self.SMTP_HOST))

settings = Settings()
