#!/bin/sh
# Wait for the database, apply migrations, seed demo data, then run the given command.
set -e

echo "[wathiq] waiting for database..."
python - <<'PY'
import os, sys, time
import psycopg

url = os.environ.get("WATHIQ_DATABASE_URL", "")
# psycopg wants a plain libpq URL, not the SQLAlchemy dialect prefix.
url = url.replace("postgresql+psycopg://", "postgresql://")
deadline = time.time() + 90
while True:
    try:
        with psycopg.connect(url, connect_timeout=3):
            break
    except Exception as exc:  # noqa: BLE001 - startup probe
        if time.time() > deadline:
            print(f"[wathiq] database not reachable: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(1.5)
print("[wathiq] database is up")
PY

if [ "${WATHIQ_RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[wathiq] applying migrations..."
  alembic upgrade head
fi

if [ "${WATHIQ_SEED_ON_START:-1}" = "1" ]; then
  echo "[wathiq] seeding demo data (skipped if already seeded)..."
  python -m app.db.seed
fi

echo "[wathiq] starting: $*"
exec "$@"
