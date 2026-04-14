from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # MySQL Database Configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "inventory_db"
    
    # Connection Pool Settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    DB_POOL_PRE_PING: bool = True

    # Construct DATABASE_URL dynamically
    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"

    # Security
    SECRET_KEY: str = "your-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # App
    APP_NAME: str = "Inventory Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ==================== EMAIL SETTINGS ====================
    # SMTP Configuration (for email notifications)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "minilik71@gmail.com"  # Your Gmail address
    SMTP_PASSWORD: str = "uvcg bdnm spto hahf"  # Your App Password (16 characters)
    SMTP_FROM_EMAIL: str = "noreply@inventory.com"
    
    # Dashboard URL (for links in emails)
    DASHBOARD_URL: str = "https://smartlink-inventory.up.railway.app"
    
    # Environment
    ENVIRONMENT: str = "development"  # development or production

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()