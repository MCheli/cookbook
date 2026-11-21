"""Application configuration sourced from env (COOKBOOK_ prefix) and .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


def _find_env_file() -> tuple[str, ...]:
    here = Path(__file__).resolve()
    candidates: list[str] = [".env"]
    for parent in here.parents:
        env_path = parent / ".env"
        if env_path.is_file():
            candidates.append(str(env_path))
            break
    return tuple(candidates)


# Defaults that are public in this repo. Production must override them.
DEV_JWT_SECRET = "dev-only-not-secret-change-me"
DEV_API_KEY_PEPPER = "dev-only-api-key-pepper-change-me"
DEV_SECRETS_KEY = "dev-only-secrets-key-change-me"
DEV_DB_PASSWORD = "changeme"
_PLACEHOLDER_SECRETS = {DEV_JWT_SECRET, "CHANGE_ME_GENERATE_WITH_OPENSSL_RAND_HEX_32", ""}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_find_env_file(),
        env_file_encoding="utf-8",
        env_prefix="COOKBOOK_",
        extra="ignore",
        case_sensitive=False,
    )

    ENV: str = "development"
    ENABLE_DOCS: bool | None = None
    SITE_URL: str = "http://localhost:8000"

    DATABASE_URL: str = "postgresql+asyncpg://cookbook:changeme@localhost:5432/cookbook"

    # Sessions: same policy as Tasks (30-day idle timeout, 90-day hard limit, refreshed every 12 h).
    JWT_SECRET: str = Field(default=DEV_JWT_SECRET)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_DAYS: int = 30
    JWT_REFRESH_AFTER_HOURS: int = 12
    JWT_MAX_SESSION_DAYS: int = 90
    COOKIE_SECURE: bool = False
    COOKIE_DOMAIN: str | None = None

    # HMAC pepper for stored API key hashes. Rotating it invalidates every API key.
    API_KEY_PEPPER: str = Field(default=DEV_API_KEY_PEPPER)
    # Encrypts each user's own Anthropic key at rest. Rotating it forgets every stored key.
    SECRETS_KEY: str = Field(default=DEV_SECRETS_KEY)

    # Local development only: a password user. The form is hidden when Google is configured.
    TEST_USER_EMAIL: str | None = None
    TEST_USER_PASSWORD: str | None = None

    GOOGLE_CLIENT_ID: str | None = None
    GOOGLE_CLIENT_SECRET: str | None = None
    GOOGLE_REDIRECT_URI: str | None = None

    # Site owners: their public recipes are the public cookbook, and only they can publish.
    # The first one receives the bundled recipes on a fresh database.
    OWNER_EMAILS: str = ""

    # Each user brings their own Anthropic key (Settings). These are the models used with it.
    AI_MODEL: str = "claude-sonnet-5-5"
    AI_MODEL_SMART: str = "claude-opus-5-5"

    DEMO_MODE: bool = False
    DEMO_URL: str | None = None
    DEMO_USER_EMAIL: str = "claudius@cookbook.dev"

    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:8000"

    @field_validator("COOKIE_DOMAIN", "DEMO_URL", "ENABLE_DOCS", mode="before")
    @classmethod
    def _empty_to_none(cls, v):
        if v == "" or v is None:
            return None
        return v

    @property
    def allowed_origins_list(self) -> list[str]:
        return [s.strip() for s in self.ALLOWED_ORIGINS.split(",") if s.strip()]

    @property
    def owner_emails(self) -> list[str]:
        if self.DEMO_MODE:
            return [self.DEMO_USER_EMAIL.lower()]
        return [s.strip().lower() for s in self.OWNER_EMAILS.split(",") if s.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def docs_enabled(self) -> bool:
        if self.ENABLE_DOCS is None:
            return not self.is_production
        return self.ENABLE_DOCS


def check_production_settings(s: Settings) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors stop startup: the defaults are public."""
    if not s.is_production:
        return [], []
    errors = []
    if s.JWT_SECRET in _PLACEHOLDER_SECRETS:
        errors.append("COOKBOOK_ENV=production with the default COOKBOOK_JWT_SECRET.")
    elif len(s.JWT_SECRET) < 32:
        errors.append("COOKBOOK_JWT_SECRET is shorter than 32 characters.")
    if s.API_KEY_PEPPER in (DEV_API_KEY_PEPPER, ""):
        errors.append("COOKBOOK_API_KEY_PEPPER is the public default.")
    if s.SECRETS_KEY in (DEV_SECRETS_KEY, "") or len(s.SECRETS_KEY) < 32:
        errors.append("COOKBOOK_SECRETS_KEY is the public default or shorter than 32 characters.")
    if make_url(s.DATABASE_URL).password == DEV_DB_PASSWORD:
        errors.append("COOKBOOK_DATABASE_URL uses the default database password.")
    warnings = []
    if not s.COOKIE_SECURE:
        warnings.append("COOKBOOK_COOKIE_SECURE is false; session cookies can travel over HTTP.")
    return errors, warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
