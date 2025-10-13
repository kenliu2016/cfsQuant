import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_TITLE: str = "Trading API"
    APP_VERSION: str = "0.1.0"
    # CORS配置
    CORS_ORIGINS: list = ["*"]
    # 日志配置
    LOG_LEVEL: str = "INFO"
    # 多租户配置
    DEFAULT_TENANT_ID: str = "public"
    
    class Config:
        env_file = ".env"

settings = Settings()
