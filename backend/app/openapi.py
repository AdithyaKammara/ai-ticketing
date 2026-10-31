"""Write the OpenAPI spec the frontend client is generated from: `python -m app.openapi`."""

import json
from pathlib import Path

from app.core.config import Settings
from app.main import create_app

OUT = Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"

if __name__ == "__main__":
    # Placeholder settings: building the spec never connects to anything.
    settings = Settings(
        _env_file=None,
        database_url="postgresql://u:p@localhost:5432/x",
        redis_url="redis://localhost:6379/0",
        jwt_secret="x" * 32,
    )
    OUT.write_text(
        json.dumps(create_app(settings).openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT}")
