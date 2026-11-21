#!/bin/sh
set -e

echo "[entrypoint] waiting for database..."
i=0
until python - <<PY 2>/dev/null
import asyncio, asyncpg, os
url = os.environ["COOKBOOK_DATABASE_URL"].replace("postgresql+asyncpg", "postgresql")
async def go():
    c = await asyncpg.connect(url)
    await c.close()
asyncio.run(go())
PY
do
  i=$((i+1))
  if [ "$i" -ge 60 ]; then
    echo "[entrypoint] database not reachable after 60s; failing"
    exit 1
  fi
  sleep 1
done
echo "[entrypoint] database ready"
cd /app/backend

case "$COOKBOOK_DEMO_MODE" in
  1|true|True|TRUE|yes)
    # Public demo: rebuild Claudius Banks's data on every start (the server restarts it nightly).
    # The seed refuses to touch a database that holds any real user.
    echo "[entrypoint] demo mode: emptying the demo database"
    python -m app.services.demo_seed --drop
    alembic upgrade head
    echo "[entrypoint] demo mode: seeding the demo persona"
    python -m app.services.demo_seed
    ;;
  *)
    echo "[entrypoint] running alembic upgrade head"
    alembic upgrade head
    ;;
esac

echo "[entrypoint] starting app: $*"
exec "$@"
