# Realtime Recovery Runbook

**النطاق**: WebSocket / Offline / Realtime Infrastructure
**آخر تحديث**: 2026-05-24
**المرجع**: ISS-OFFLINE-001, D-WS-001, D-WS-002

---

## 1. تشخيص سريع (< 2 دقيقة)

```bash
# الخطوة 1: تحقق من أن الخدمات تعمل
curl -s http://localhost:8000/health   # Gateway
curl -s http://localhost:8003/health   # Conversation Service

# الخطوة 2: اختبار WebSocket على Gateway (الأهم)
timeout 5 curl -v \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13" \
  http://localhost:8000/api/chat/ws 2>&1 | grep "< HTTP"

# النتائج المتوقعة:
# HTTP/1.1 101 → ✅ يعمل (WebSocket upgrade ناجح)
# HTTP/1.1 403 → ✅ يعمل (يحتاج token — مقبول)
# HTTP/1.1 404 → ❌ D-WS-001 VIOLATION — ws_proxy غير مُسجَّل
# Connection refused → ❌ Gateway لا يعمل

# الخطوة 3: اختبار WebSocket على Conversation Service مباشرة
timeout 5 curl -v \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13" \
  http://localhost:8003/chat/ws 2>&1 | grep "< HTTP"

# يجب أن يُرجع 101 دائماً
```

---

## 2. شجرة القرار

```
المستخدم يرى "offline"
        │
        ▼
هل Gateway يعمل؟
curl http://localhost:8000/health
        │
   ┌────┴────┐
  نعم       لا
   │         └→ [A] إعادة تشغيل Gateway
   ▼
هل /api/chat/ws يُرجع 101 أو 403؟
        │
   ┌────┴────┐
  نعم       لا (404)
   │         └→ [B] ws_proxy غير مُسجَّل
   ▼
هل conversation-service يعمل؟
curl http://localhost:8003/health
        │
   ┌────┴────┐
  نعم       لا
   │         └→ [C] إعادة تشغيل conversation-service
   ▼
هل المشكلة في Frontend فقط؟
(المتصفح يُظهر offline لكن curl يعمل)
        │
        └→ [D] مشكلة URL generation أو reconnect
```

---

## 3. إجراءات الإصلاح

### [A] إعادة تشغيل Gateway

```bash
# إيجاد PID
ps aux | grep "uvicorn app.main" | grep -v grep

# إيقاف
kill -SIGTERM <PID>
sleep 2

# إعادة التشغيل (من مجلد المشروع)
cd /workspaces/NAAS-Agentic-Core
python -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --ws websockets \
    --ws-ping-interval 20 \
    --ws-ping-timeout 30 \
    --timeout-keep-alive 75 \
    --reload \
    --log-level info &

# تحقق
sleep 3 && curl http://localhost:8000/health
```

### [B] ws_proxy غير مُسجَّل (404 على /api/chat/ws)

```bash
# تحقق من وجود الملف
ls app/api/routers/ws_proxy.py

# تحقق من التسجيل في registry
grep "ws_proxy" app/api/routers/registry.py

# تحقق من الترتيب (يجب أن يسبق customer_chat)
grep -n "ws_proxy\|customer_chat" app/api/routers/registry.py

# إذا كان الملف موجوداً لكن غير مُسجَّل:
# أضف (ws_proxy.router, "") أول عنصر في base_router_registry()
# ثم أعد تشغيل Gateway
```

### [C] إعادة تشغيل conversation-service

```bash
# عبر Gitpod automations
gitpod automations task start restart-conversation-service

# أو يدوياً
ps aux | grep "conversation_service.main" | grep -v grep
kill -SIGTERM <PID>
sleep 2

cd /workspaces/NAAS-Agentic-Core
python -m uvicorn microservices.conversation_service.main:app \
    --host 0.0.0.0 \
    --port 8003 \
    --ws websockets \
    --ws-ping-interval 20 \
    --ws-ping-timeout 30 \
    --timeout-keep-alive 75 \
    --log-level info &

# تحقق
sleep 3 && curl http://localhost:8003/health
```

### [D] مشكلة Frontend URL Generation

```bash
# تحقق من أن wsUrl.js يُستخدم
grep -n "buildWsUrl\|getWsBase\|wsUrl" \
    frontend/app/hooks/useAgentSocket.js

# تحقق من عدم وجود localhost hardcoding
grep -rn "localhost\|:8000\|:8003" \
    frontend/app/hooks/ \
    frontend/app/utils/wsUrl.js \
    frontend/app/components/

# إذا وجدت localhost → استبدل بـ buildWsUrl من wsUrl.js
```

---

## 4. فحص Codespaces

```bash
# تحقق من أن port 8000 مُعرَّض
gitpod environment port list | grep 8000

# في Codespaces: تحقق من أن المتصفح يصل لـ 8000 مباشرة
# (وليس عبر Next.js proxy على 3000)
echo "Gateway URL: https://$(hostname)-8000.$(echo $GITPOD_WORKSPACE_URL | sed 's|https://||')"

# اختبار WebSocket من خارج (استبدل URL بالـ Codespace URL الحقيقي)
# wscat -c "wss://[workspace-id]-8000.app.github.dev/api/chat/ws"
```

---

## 5. فحص Mobile Networks

```bash
# المشكلة الشائعة: شبكات الهاتف تقطع connections خاملة بعد 30-60 ثانية
# الحل: uvicorn ping-interval 20s يُبقي الاتصال حياً

# تحقق من uvicorn settings الحالية
ps aux | grep uvicorn | grep "app.main"
# يجب أن يحتوي على: --ws-ping-interval 20 --ws-ping-timeout 30

# إذا كانت القيم مختلفة → أعد تشغيل بالإعدادات الصحيحة (انظر [A])
```

---

## 6. فحص Gateway Forwarding

```bash
# تحقق من أن ws_proxy يُمرِّر بشكل صحيح
# 1. اختبر conversation-service مباشرة
timeout 5 curl -v \
  -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13" \
  http://localhost:8003/chat/ws 2>&1 | grep "< HTTP"
# يجب: 101

# 2. اختبر عبر Gateway
timeout 5 curl -v \
  -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13" \
  http://localhost:8000/api/chat/ws 2>&1 | grep "< HTTP"
# يجب: 101 أو 403

# إذا 8003 يُرجع 101 لكن 8000 يُرجع 404:
# → ws_proxy غير مُسجَّل → انظر [B]

# إذا 8003 يُرجع 101 لكن 8000 يُرجع timeout:
# → ws_proxy يعمل لكن conversation-service بطيء
# → تحقق من logs: tail -f .observability/conversation_service.log
```

---

## 7. خطوات Recovery الكاملة

```bash
# Recovery sequence بعد أي crash

# 1. تحقق من الحالة
curl http://localhost:8000/health
curl http://localhost:8003/health

# 2. شغِّل الاختبارات السريعة
cd /workspaces/NAAS-Agentic-Core
python -m pytest tests/microservices/test_websocket_gateway_routing.py -v -k "not Live" -q

# 3. شغِّل الاختبارات الحية
python -m pytest tests/microservices/test_websocket_gateway_routing.py -v -m integration -q

# 4. إذا فشل test_gateway_ws_not_404:
#    → ws_proxy غير مُسجَّل → انظر [B]

# 5. إذا فشل test_conversation_service_ws_returns_101:
#    → conversation-service لا يعمل → انظر [C]

# 6. إذا نجحت الاختبارات لكن المستخدم لا يزال يرى offline:
#    → مشكلة Frontend → انظر [D]
#    → أو مشكلة auth token → تحقق من JWT expiry
```

---

## 8. Rollback Plan

إذا أحدث ws_proxy مشاكل غير متوقعة:

```bash
# Rollback سريع: إزالة ws_proxy من registry
# في app/api/routers/registry.py:
# احذف السطر: (ws_proxy.router, ""),
# واحذف import ws_proxy

# ثم أعد تشغيل Gateway
# النتيجة: /api/chat/ws يعود لـ customer_chat.router (403 بدون token)
# Frontend سيحتاج NEXT_PUBLIC_WS_URL=http://localhost:8003 للاتصال المباشر

# للتحقق من Rollback:
curl -I http://localhost:8000/api/chat/ws
# 403 = rollback ناجح (customer_chat.router يعمل)
# 404 = rollback ناجح (لا يوجد WebSocket handler)
```

---

## 9. Metrics & Monitoring

```bash
# فحص Prometheus metrics لـ WebSocket
curl -s http://localhost:8000/metrics | grep -E "websocket|ws_"
curl -s http://localhost:8003/metrics | grep -E "websocket|ws_|conversation"

# فحص logs
tail -f /workspaces/NAAS-Agentic-Core/.observability/conversation_service.log | grep -E "ws_proxy|websocket|chat_ws"

# فحص uvicorn logs للـ WebSocket connections
journalctl -u uvicorn 2>/dev/null | grep -E "websocket|101|upgrade" | tail -20
```

---

## 10. قائمة التحقق النهائية

بعد أي إصلاح، تحقق من:

- [ ] `curl http://localhost:8000/health` → `{"application":"ok"}`
- [ ] `curl http://localhost:8003/health` → `{"status":"healthy"}`
- [ ] WebSocket على 8000 → 101 أو 403 (ليس 404)
- [ ] WebSocket على 8003 → 101
- [ ] `pytest tests/microservices/test_websocket_gateway_routing.py` → 11/11 pass
- [ ] لا يوجد `localhost` hardcoded في browser JavaScript
- [ ] `ws_proxy.router` أول router في registry
- [ ] uvicorn يعمل بـ `--ws-ping-interval 20 --ws-ping-timeout 30`
