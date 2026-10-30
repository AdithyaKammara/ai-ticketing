from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

# Nothing listens on port 1, so dependency checks fail fast and deterministically.
UNREACHABLE_DB = "postgresql://ticketing:ticketing@127.0.0.1:1/ticketing"
UNREACHABLE_REDIS = "redis://127.0.0.1:1/0"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=UNREACHABLE_DB,
        redis_url=UNREACHABLE_REDIS,
        jwt_secret="test-secret-that-is-at-least-32-characters",
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings), raise_server_exceptions=False) as test_client:
        yield test_client
