# WebSocket Topology — CogniForge Realtime Infrastructure

**آخر تحديث**: 2026-05-24 (ISS-OFFLINE-001 architectural fix)
**الحالة**: ACTIVE — هذه الخريطة تعكس الواقع الحالي

---

## خريطة WebSocket الكاملة

```
Browser (Mobile / Desktop / Codespaces)
    │
    │  wss://[workspace-host]/api/chat/ws
    │  (window.location.host — لا localhost، لا port hardcoding)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Next.js Frontend  :3000 (Codespaces) / :5000 (Replit) │
│                                                     │
│  ⚠️ next.config.js rewrites:                        │
│     /api/:path* → 8000/api/:path*                   │
│     هذا يعمل فقط مع HTTP — لا يُمرِّر WebSocket!   │
│                                                     │
│  الحل: المتصفح يتصل مباشرة بـ Gateway (8000)       │
│  عبر window.location.host (يتجاوز Next.js proxy)   │
└─────────────────────────────────────────────────────┘
    │
    │  WebSocket Upgrade Request
    │  GET /api/chat/ws HTTP/1.1
    │  Connection: Upgrade
    │  Upgrade: websocket
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Gateway  :8000  (app/main.py → uvicorn)            │
│                                                     │
│  ws_proxy.py  ← أول router في registry             │
│  @router.websocket("/api/chat/ws")                  │
│  @router.websocket("/admin/api/chat/ws")            │
│                                                     │
│  uvicorn settings:                                  │
│    --ws websockets                                  │
│    --ws-ping-interval 20                            │
│    --ws-ping-timeout 30                             │
│    --timeout-keep-alive 75                          │
└─────────────────────────────────────────────────────┘
    │
    │  WebSocket Proxy (bidirectional bridge)
    │  ws://localhost:8003/chat/ws
    │  Preserves: subprotocols (jwt, token), query_string
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Conversation Service  :8003                        │
│  (microservices/conversation_service/main.py)       │
│                                                     │
│  @app.websocket("/chat/ws")      ← customer         │
│  @app.websocket("/admin/chat/ws") ← admin           │
│                                                     │
│  uvicorn settings:                                  │
│    --ws websockets                                  │
│    --ws-ping-interval 20                            │
│    --ws-ping-timeout 30                             │
│    --timeout-keep-alive 75                          │
└─────────────────────────────────────────────────────┘
```

---

## WebSocket Ownership

| Endpoint | Owner | Port | File |
|----------|-------|------|------|
| `/api/chat/ws` | Gateway (proxy) | 8000 | `app/api/routers/ws_proxy.py` |
| `/admin/api/chat/ws` | Gateway (proxy) | 8000 | `app/api/routers/ws_proxy.py` |
| `/chat/ws` | Conversation Service | 8003 | `microservices/conversation_service/main.py` |
| `/admin/chat/ws` | Conversation Service | 8003 | `microservices/conversation_service/main.py` |

**قانون الملكية (D-WS-001):**
- Gateway يملك الـ public endpoints (`/api/chat/ws`)
- Conversation Service يملك الـ implementation (`/chat/ws`)
- لا يجوز للـ Frontend الاتصال مباشرة بـ 8003

---

## Frontend WebSocket URL Generation

```javascript
// frontend/app/utils/wsUrl.js
buildWsUrl('/api/chat/ws', sessionId)
  → يستخدم window.location.host
  → ws:// في http، wss:// في https
  → يعمل في: Local / Codespaces / Gitpod / Mobile / VPN
```

**ممنوع:**
```javascript
// ❌ NEVER
new WebSocket('ws://localhost:8000/api/chat/ws')
new WebSocket(`ws://${hostname}:8000/api/chat/ws`)
```

**صحيح:**
```javascript
// ✅ ALWAYS
import { buildWsUrl } from '../utils/wsUrl';
const url = buildWsUrl('/api/chat/ws', sessionId);
```

---

## Reconnect Lifecycle (useRealtimeConnection.js)

```
idle
  │ connect()
  ▼
connecting ──────────────────────────────────────────┐
  │ onopen                                           │
  ▼                                                  │
connected ←──── recovered                            │
  │ startHeartbeat()                                 │
  │ ping every 25s                                   │
  │                                                  │
  │ onerror                                          │
  ▼                                                  │
degraded                                             │
  │ onclose                                          │
  ▼                                                  │
reconnecting (retries 1..9)                          │
  │ exponential backoff (500ms → 30s) + jitter       │
  │ connect() ──────────────────────────────────────┘
  │
  │ retries >= 10 (MAX_RETRIES)
  ▼
offline ← لا يُعلَن إلا هنا (D-WS-002)
```

**حالات State Machine:**
| الحالة | المعنى | UI |
|--------|--------|-----|
| `idle` | لم يبدأ بعد | - |
| `connecting` | محاولة أولى | spinner |
| `connected` | متصل ✅ | green dot |
| `degraded` | خطأ مؤقت | yellow dot |
| `reconnecting` | يُعيد الاتصال | spinner + counter |
| `recovered` | عاد بعد انقطاع | brief green flash |
| `offline` | فشل نهائي (10 محاولات) | red dot |
| `auth_error` | خطأ مصادقة (4401/4403) | error message |

---

## Fallback Behavior

إذا فشل WebSocket proxy (8003 غير متاح):
1. `ws_proxy.py` يُرسل `{"type":"error","payload":{"code":"WS_UPSTREAM_TIMEOUT"}}`
2. Frontend يُظهر error notification
3. يُغلق الاتصال بـ code 1013 (Try Again Later)
4. `useRealtimeConnection` يبدأ reconnect cycle

---

## Codespaces / Gitpod Compatibility

في Codespaces/Gitpod:
- المتصفح يصل عبر `https://[workspace-id]-3000.app.github.dev`
- `window.location.host` = `[workspace-id]-3000.app.github.dev`
- `buildWsUrl('/api/chat/ws')` → `wss://[workspace-id]-3000.app.github.dev/api/chat/ws`
- Next.js يستقبل الطلب → يُمرِّره إلى Gateway (8000) عبر HTTP proxy
- **لكن WebSocket upgrade لا يُمرَّر عبر Next.js!**
- الحل: المتصفح يتصل مباشرة بـ Gateway عبر port forwarding

**ملاحظة**: في Gitpod/Ona، port 8000 مُعرَّض مباشرة للمتصفح عبر port forwarding.
`window.location.host` في هذه الحالة يكون `[workspace-id]-8000.ws-eu.gitpod.io`.

---

## Anti-Regression Checklist

قبل أي تغيير على WebSocket infrastructure:

- [ ] `curl -I -H "Upgrade: websocket" ... http://localhost:8000/api/chat/ws` → 101 أو 403 (ليس 404)
- [ ] `curl -I -H "Upgrade: websocket" ... http://localhost:8003/chat/ws` → 101
- [ ] `ws_proxy.router` أول router في `base_router_registry()`
- [ ] لا يوجد `localhost` أو port hardcoding في browser JavaScript
- [ ] `pytest tests/microservices/test_websocket_gateway_routing.py` → 11/11 pass
