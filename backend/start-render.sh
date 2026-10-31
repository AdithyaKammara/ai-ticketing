#!/bin/sh
# Render free tier: one container runs migrations, the demo seed (a no-op once data
# exists), the triage worker, and the API.
# ponytail: the worker is an unsupervised background process; if it dies, triage stops
# until the next deploy or restart. Move it to its own Render worker service (paid)
# when this matters.
set -e
alembic upgrade head
python -m app.seed
arq app.workers.main.WorkerSettings &
exec uvicorn app.main:create_app --factory --host 0.0.0.0 --port "${PORT:-8000}"
