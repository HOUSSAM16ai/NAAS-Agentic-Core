#!/usr/bin/env bash
# بدء نظيف لـ Codespace جديد بعد إنشاء .devcontainer/secrets.env.
# يُعيد تشغيل النظام بالكامل: يحقن الأسرار، يمسح كاش البناء (bundle جديد)،
# يضمن ws، ويُشغّل الخلفية (uvicorn:8000) + الواجهة (server.js:5000).
#
# الاستخدام:
#   bash scripts/codespace_fresh_start.sh

set -uo pipefail
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

echo "==> [1/6] git pull (أحدث إصلاح)"
git pull origin claude/chat-session-auth-bugs-aLf74 || echo "  (تخطّي pull)"

echo "==> [2/6] فحص الأسرار (secrets.env)"
if [ -f .devcontainer/secrets.env ]; then
  echo "  ✅ secrets.env موجود"
else
  echo "  ❌ secrets.env مفقود! النظام سيعمل بوضع متدهور (SQLite، بلا إجابات حقيقية)."
  echo "     أنشئه أولاً (انظر التعليمات في المحادثة) ثم أعد تشغيل هذا السكربت."
fi

echo "==> [3/6] إيقاف أي عمليات حالية"
pkill -f "supervisor.sh" 2>/dev/null || true
pkill -f "uvicorn app.main:app" 2>/dev/null || true
pkill -f "node .*server.js" 2>/dev/null || true
pkill -f "next dev" 2>/dev/null || true
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 5000/tcp 2>/dev/null || true
sleep 3

echo "==> [4/6] تنظيف كاش البناء + الحالة (يضمن JS جديداً)"
rm -rf frontend/.next 2>/dev/null || true
rm -f .devcontainer/state/supervisor_running 2>/dev/null || true
rm -f .devcontainer/locks/*.lock 2>/dev/null || true

echo "==> [5/6] تشغيل الـ supervisor (يحقن الأسرار + يبني نظيفاً + الخلفية والواجهة)"
nohup bash .devcontainer/supervisor.sh > /tmp/codespace_start.log 2>&1 &
echo "  الانتظار حتى تجهز الخلفية (أول تجميع قد يستغرق ~1-2 دقيقة)…"
backend_ok=""
for i in $(seq 1 36); do
  sleep 5
  if curl -s -m5 http://localhost:8000/health >/dev/null 2>&1; then
    backend_ok=1
    echo "  ✅ الخلفية (8000) تعمل"
    break
  fi
  echo "  …انتظار ($i/36)"
done

echo "==> [6/6] الحالة النهائية"
echo -n "  /health: "; curl -s -m5 http://localhost:8000/health 2>/dev/null; echo
if curl -s -m5 -o /dev/null "http://localhost:5000/" 2>/dev/null; then
  echo "  ✅ الواجهة (5000) تستجيب"
else
  echo "  ⏳ الواجهة (5000) ما زالت تُجمِّع — انتظر قليلاً ثم حدّث الصفحة"
fi
echo ""
if [ -n "$backend_ok" ]; then
  echo "  ✅ جاهز. افتح المنفذ 5000 في تبويب جديد، سجّل الدخول، واطرح سؤالاً."
  echo "     للتحقق لاحقاً:  grep \"client connected (build=\" /tmp/frontend_iss101.log .frontend_launcher.log 2>/dev/null | tail -5"
  echo "     يجب أن ترى build=D-WS-PROXY-003 (لا UNKNOWN، لا client closed code=1001)."
else
  echo "  ⚠️ الخلفية لم تجهز بعد. تابع السجل:  tail -50 /tmp/codespace_start.log"
fi
