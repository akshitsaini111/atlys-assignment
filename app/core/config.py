from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # Redis
    REDIS_URL: str
    
    # JWT
    SECRET_KEY: str = "AkshitisAwesome"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # App
    APP_NAME: str = "Task Management API"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"

settings = Settings()