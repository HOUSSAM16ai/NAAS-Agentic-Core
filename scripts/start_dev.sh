#!/usr/bin/env bash
set -euo pipefail

# 1) kill old uvicorn
pkill -f uvicorn || true
sleep 1

# 2) ensure .env exists (fallback)
if [ ! -f .env ]; then
  echo "PORT=8000" > .env
  echo "APP_ENV=development" >> .env
  # add other defaults as needed
fi

# 3) run migrations (optional)
# alembic upgrade head || true

# 4) start backend
echo "Starting uvicorn..."
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port ${PORT:-8000} \
  --ws websockets \
  --ws-ping-interval 300 \
  --ws-ping-timeout 300 \
  --reload > uvicorn.log 2>&1 &
sleep 2

# 5) show status
ss -lntp | grep :${PORT:-8000} || true
tail -n 50 uvicorn.log || true

echo "Done. Open forwarded URL for port ${PORT:-8000}"
