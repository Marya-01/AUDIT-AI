from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://audit_user:audit_password@localhost:5432/audit_ai"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    upload_dir: str = "storage"
    max_upload_mb: int = 20
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

settings = Settings()
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
