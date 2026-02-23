from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    database_url: str = Field(alias="DATABASE_URL")
    secret_key: str = Field(alias="SECRET_KEY")
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
