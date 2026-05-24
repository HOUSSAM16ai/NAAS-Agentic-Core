#!/bin/bash
set -e
echo "🚀 Starting backend server..."
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --ws websockets \
  --ws-ping-interval 300 \
  --ws-ping-timeout 300
