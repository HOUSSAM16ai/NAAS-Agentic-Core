# WebSocket Infrastructure

**آخر تحديث**: 2026-05-24 — ISS-OFFLINE-001 architectural fix
**الحالة**: Production-grade

---

## Architecture Overview

```
Browser → Gateway :8000 (ws_proxy) → Conversation Service :8003
```

Gateway يستقبل جميع WebSocket connections من المتصفح ويُمرِّرها إلى
conversation-service عبر bidirectional proxy. هذا يضمن:
- نقطة دخول واحدة لجميع WebSocket connections
- الحفاظ على auth headers وsubprotocols
- دعم Codespaces/Gitpod/Mobile بدون تعديل

---

## Endpoints

| Public Endpoint (Gateway :8000) | Upstream (Conversation :8003) | الاستخدام |
|--------------------------------|-------------------------------|-----------|
| `/api/chat/ws` | `/chat/ws` | محادثة المستخدم القياسي |
| `/admin/api/chat/ws` | `/admin/chat/ws` | محادثة الأدمن |

---

## Implementation Files

| الملف | الدور |
|-------|-------|
| `app/api/routers/ws_proxy.py` | WebSocket reverse proxy (Gateway → Conversation Service) |
| `app/api/routers/registry.py` | تسجيل ws_proxy أولاً في router registry |
| `frontend/app/utils/wsUrl.js` | URL generation — window.location.host |
| `frontend/app/hooks/useAgentSocket.js` | WebSocket client hook |
| `frontend/app/hooks/useRealtimeConnection.js` | Connection manager + state machine + heartbeat |
| `microservices/conversation_service/main.py` | WebSocket implementation الحقيقي |

---

## Frontend Connection Flow

```javascript
// frontend/app/utils/wsUrl.js
import { buildWsUrl } from '../utils/wsUrl';

// يبني URL ديناميكياً من window.location.host
// ws:// في http، wss:// في https
// يعمل في: Local / Codespaces / Gitpod / Mobile / VPN
const url = buildWsUrl('/api/chat/ws', sessionId);
```

**قانون إلزامي (D-WS-001):**
- ممنوع استخدام `localhost` أو port hardcoding في browser
- ممنوع الاعتماد على Next.js rewrites لتمرير WebSocket
- يجب استخدام `buildWsUrl()` من `wsUrl.js`

---

## Connection State Machine

```
idle → connecting → connected → degraded → reconnecting → offline
                             ↘ recovered (→ connected)
```

| الحالة | المعنى |
|--------|--------|
| `connecting` | محاولة أولى |
| `connected` | متصل ✅ |
| `degraded` | خطأ مؤقت، يُعيد المحاولة |
| `reconnecting` | يُعيد الاتصال (1-9 محاولات) |
| `recovered` | عاد بعد انقطاع |
| `offline` | فشل نهائي (10 محاولات) |
| `auth_error` | خطأ مصادقة (4401/4403) — لا إعادة |

**D-WS-002**: لا يُعلَن عن `offline` إلا بعد 10 محاولات فاشلة.

---

## Heartbeat

- ping كل 25 ثانية
- انتظار pong لمدة 10 ثوانٍ
- إذا لم يصل pong → إغلاق الاتصال وإعادة الاتصال
- يكشف stale connections على شبكات الهاتف المتذبذبة

---

## uvicorn Settings

```bash
# Gateway (8000) وConversation Service (8003)
--ws websockets          # backend مستقر
--ws-ping-interval 20    # ping كل 20 ثانية
--ws-ping-timeout 30     # انتظر pong 30 ثانية
--timeout-keep-alive 75  # keep-alive للشبكات المتذبذبة
```

---

## Troubleshooting

### الأعراض والحلول السريعة

**المتصفح يُظهر "offline" رغم أن backend يعمل:**
```bash
# تحقق من WebSocket routing
timeout 5 curl -v \
  -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13" \
  http://localhost:8000/api/chat/ws 2>&1 | grep "< HTTP"

# 101 أو 403 = يعمل ✅
# 404 = D-WS-001 VIOLATION — ws_proxy غير مُسجَّل ❌
```

**404 على /api/chat/ws:**
```bash
# تحقق من ws_proxy في registry
grep -n "ws_proxy" app/api/routers/registry.py
# يجب أن يظهر قبل customer_chat
```

**conversation-service لا يستجيب:**
```bash
curl http://localhost:8003/health
gitpod automations task start restart-conversation-service
```

**Runbook كامل**: `.memory/runbooks/realtime-recovery.md`

---

## Anti-Regression Tests

```bash
# اختبارات unit (لا تحتاج services)
pytest tests/microservices/test_websocket_gateway_routing.py -k "not Live" -v

# اختبارات حية (تحتاج Gateway + Conversation Service)
pytest tests/microservices/test_websocket_gateway_routing.py -m integration -v
```

**D-WS-001**: إذا فشل `test_gateway_ws_not_404` → architectural routing failure.

---

## Root Cause History

### ISS-OFFLINE-001 (2026-05-24) — الكارثة وحلها

**المشكلة**: المتصفح يُظهر offline رغم أن backend حي. VPN يحل المشكلة.

**السبب الجذري**:
1. Frontend كان يضرب `hostname:8000` مباشرة (port hardcoded)
2. Next.js rewrites لا تُمرِّر WebSocket upgrade headers
3. Gateway لم يكن يملك WebSocket proxy — كان يُرجع 403
4. WebSocket الحقيقي على 8003 لكن Frontend لا يعرف عنه
5. VPN غيَّر network path → وهم أن المشكلة في keepalive

**الحل**: `ws_proxy.py` يُمرِّر WebSocket من 8000 إلى 8003.

**التحقق**: `curl ... http://localhost:8000/api/chat/ws` → 101 ✅
