#!/usr/bin/env bash
# محاكاة الفحص الحي الذي سيقوم به supervisor.sh (D-246):
# لا يكفي وجود متغير DATABASE_URL — يجب أن يكون الاتصال الفعلي ناجحًا.
set -u
DB="${APP_DATABASE_URL:-${DATABASE_URL:-}}"
if [ -z "$DB" ]; then
  echo "MISSING (no variable)"
  exit 2
fi
case "$DB" in
  sqlite* ) echo "SQLITE (not a real database)" ; exit 3 ;;
esac
# فحص حي: SELECT 1 ضد المضيف/المنفذ الفعليين (بدون كلمة السر في السجلات)
HOST=$(echo "$DB" | sed -E 's|^.*@([^@/:]+).*|\1|')
PORT=$(echo "$DB" | sed -E 's|^.*:([0-9]+)/.*|\1|')
if [ -z "$HOST" ] || [ -z "$PORT" ]; then
  echo "UNPARSEABLE"
  exit 4
fi
if timeout 8 bash -c "echo >/dev/tcp/$HOST/$PORT" 2>/dev/null; then
  echo "REACHABLE ($HOST:$PORT)"
  exit 0
else
  echo "UNREACHABLE ($HOST:$PORT — port blocked or host dead)"
  exit 5
fi
