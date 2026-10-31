"""The frontend's typed client is generated from frontend/openapi.json; keep it in sync."""

import json
from pathlib import Path

from app.main import create_app
from tests.conftest import UNREACHABLE_DB, UNREACHABLE_REDIS, make_settings

SNAPSHOT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"


def test_frontend_openapi_snapshot_is_current() -> None:
    spec = create_app(make_settings(UNREACHABLE_DB, UNREACHABLE_REDIS)).openapi()

    assert json.loads(SNAPSHOT.read_text(encoding="utf-8")) == spec, (
        "API changed: regenerate with `uv run python -m app.openapi` then `pnpm gen:api`"
    )
