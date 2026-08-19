from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./lwms.db"
    # 32+ bytes avoids HS256 weak-key warnings in local development. Always
    # override this with a unique secret from the deployment environment.
    jwt_secret: str = "lwms-local-development-key-change-before-production-2026"
    jwt_expire_minutes: int = 480
    cors_origins: str = "http://localhost:5173"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    @property
    def origins(self) -> list[str]: return [x.strip() for x in self.cors_origins.split(',')]
@lru_cache
def settings() -> Settings: return Settings()
