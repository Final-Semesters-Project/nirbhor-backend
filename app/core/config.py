from typing import Any
from pydantic import field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# load env variables from .env and make it available to the app with the name settings
class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: SecretStr
    POSTGRES_DB: str

    DATABASE_URL: str
    SYNC_DATABASE_URL: str

    SECRET_KEY: SecretStr
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 864000

    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str

    APP_ENV: str
    STAGING_API_KEY: SecretStr | None = None

    # Splits the cors origins string and converts into a list
    CORS_ORIGINS: Any = []

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, value: Any) -> list[str]:
        # Handle string input from env
        if isinstance(value, str):
            # if its a string, split by comma
            if not value.startswith("["):
                # Handles "url1, url2" -> ["url1", "url2"]
                return [item.strip() for item in value.split(",") if item.strip()]

            import json
            try:
                return json.loads(value)
            except:
                return []

        if isinstance(value, (list, tuple)):
            return list(value)

        return []

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"  # it ignores the env variables that are not in the pydantic model
    )


settings = Settings()  # type: ignore
