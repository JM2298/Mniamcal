#!/bin/sh
set -eu

python - <<'PY'
import os
import time

import psycopg2

db_name = os.getenv("DB_NAME", "mydb")
db_user = os.getenv("DB_USER", "myuser")
db_password = os.getenv("DB_PASSWORD", "mypassword")
db_host = os.getenv("DB_HOST", "db")
db_port = os.getenv("DB_PORT", "5432")
max_attempts = int(os.getenv("DB_WAIT_MAX_ATTEMPTS", "300"))

for attempt in range(1, max_attempts + 1):
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
        )
        conn.close()
        print("Database is ready.")
        break
    except psycopg2.OperationalError:
        print(f"Waiting for database... ({attempt}/{max_attempts})")
        time.sleep(2)
else:
    raise SystemExit("Database did not become ready in time.")
PY

python manage.py migrate --noinput

# Run collectstatic only when starting an app server process.
# One-off management commands should not rewrite static files.
if [ "${1:-}" = "gunicorn" ] || [ "${1:-}" = "uvicorn" ]; then
    python manage.py collectstatic --noinput
fi

exec "$@"
