from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ==================== DATABASE ====================
    DB_HOST: str
    DB_PORT: int = 3306
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str

    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True

    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    # ==================== SECURITY ====================
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ==================== APP ====================
    APP_NAME: str = "IRailway Inventory"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ==================== BREVO ====================
    BREVO_API_KEY: Optional[str] = None
    BREVO_SENDER_EMAIL: str
    BREVO_SENDER_NAME: str = "SmartLink"
    EMAIL_ENABLED: bool = True

    # ==================== SMTP ====================
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = 465
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None

    # ==================== URLS ====================
    DASHBOARD_URL: str
    FRONTEND_URL: str

    # ==================== ENV ====================
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
