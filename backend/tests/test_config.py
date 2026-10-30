import pytest
from pydantic import ValidationError

from app.core.config import Settings

REQUIRED = ("DATABASE_URL", "REDIS_URL", "JWT_SECRET")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (*REQUIRED, "CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)


def test_settings_refuse_to_load_without_required_values() -> None:
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    missing = {str(error["loc"][0]).upper() for error in exc_info.value.errors()}
    assert missing == set(REQUIRED)


def test_settings_reject_short_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "too-short")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_cors_origins_are_read_as_comma_separated_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("JWT_SECRET", "x" * 32)
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, https://tickets.example.com")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://localhost:5173", "https://tickets.example.com"]
