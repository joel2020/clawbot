from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str

    # Redis
    redis_url: str

    # LiteLLM
    litellm_base_url: str = "http://litellm:4000"
    litellm_api_key: str

    # App
    secret_key: str
    environment: str = "production"
    agents_dir: str = "/app/agents"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
