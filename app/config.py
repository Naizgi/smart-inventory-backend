from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # MySQL Database Configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 3308
    DB_USER: str = "root"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "inventory_db"
    
    # Build DATABASE_URL for MySQL
    @property
    def DATABASE_URL(self) -> str:
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # App
    APP_NAME: str = "Inventory Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"

settings = Settings()