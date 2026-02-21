#!/bin/bash
# Start the Merchant+ backend (Daphne ASGI server)
# Safely kills any existing process on port 8000 before starting.

set -e

BACKEND_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$BACKEND_DIR/env/bin/activate"
PORT=8000

echo "==> Checking port $PORT..."
PIDS=$(lsof -ti:$PORT 2>/dev/null || true)
if [ -n "$PIDS" ]; then
  echo "==> Killing existing process(es) on port $PORT: $PIDS"
  echo "$PIDS" | xargs kill -9 2>/dev/null || true
  sleep 1
fi

echo "==> Activating virtualenv..."
source "$VENV"

echo "==> Running migrations..."
python "$BACKEND_DIR/manage.py" migrate --noinput

echo "==> Starting Daphne on port $PORT..."
exec daphne -b 127.0.0.1 -p $PORT config.asgi:application
