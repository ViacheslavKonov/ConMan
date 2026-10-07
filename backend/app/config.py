from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "production"
    app_name: str = "ConMan"

    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "conman"
    db_user: str = "conman"
    db_password: str

    session_ttl_hours: int = 12
    cookie_secure: bool = False
    cookie_domain: str | None = None
    session_cookie_name: str = "conman_session"
    csrf_cookie_name: str = "conman_csrf"

    @property
    def database_url(self) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
