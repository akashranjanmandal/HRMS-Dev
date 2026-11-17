from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/aaranyak_hrms"
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    RESET_TOKEN_EXPIRE_MINUTES: int = 60
    MIN_PASSWORD_LENGTH: int = 8
    CORS_ORIGINS: str = "http://localhost:3000"

    UPLOAD_DIR: str = str(BACKEND_DIR / "uploads")
    MAX_UPLOAD_MB: int = 10

    ORG_NAME: str = "Aaranyak"
    TIMEZONE: str = "Asia/Kolkata"

    # Email. SMTP_HOST empty (the default) means dev/test mode: every
    # message is recorded in app.services.mailer.OUTBOX instead of being
    # sent, so local development and the test suite never need a real
    # mail server. Set SMTP_HOST (and the rest, as needed) to send for real.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USE_TLS: bool = True
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "Aaranyak HRMS <noreply@aaranyak.org>"

    # Dev/demo convenience only: when set, every email OTP is this fixed
    # value instead of a random one, so manual testing can log in as any
    # seeded user without reading the mail outbox. Off by default — must
    # be deliberately set (e.g. in a local-only .env), and is refused
    # outright alongside a real SMTP_HOST (see Settings.__init__ below),
    # since that combination means this is not a throwaway dev box.
    DEV_FIXED_OTP: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.DEV_FIXED_OTP and self.SMTP_HOST:
            raise ValueError(
                "DEV_FIXED_OTP is set alongside a real SMTP_HOST — refusing to start. "
                "A fixed, publicly-known OTP must never be enabled anywhere real email "
                "delivery is configured. Unset DEV_FIXED_OTP (or SMTP_HOST, for a throwaway dev box)."
            )


settings = Settings()
