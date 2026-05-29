/**
 * Next.js Custom Server — WebSocket Proxy (ws-library, reliable).
 *
 * ## لماذا هذا الملف موجود؟
 *
 * Next.js rewrites() لا تُمرِّر WebSocket upgrade headers. في Codespaces المتصفح
 * يصل عبر *-5000.app.github.dev → هذا الـ server يستقبل الـ upgrade ويُمرِّره إلى
 * ws://127.0.0.1:8000 داخلياً.
 *
 * ## ISS-101 (D-WS-PROXY-001 — 2026-05-29): السبب الجذري للتأرجح
 *
 * تشخيص حيّ في Codespaces أثبت بشكل قاطع:
 *   - اتصال مباشر بالـ backend :8000 → يُجيب 3/3 (session_ready → ... → assistant_final).
 *   - عبر هذا الـ proxy :5000 → 3/3 «NO ANSWER, close=1006» فور استقبال session_ready.
 * المتغيّر الوحيد بين المسارين هو هذا الملف. الإصدار القديم استخدم `http-proxy`
 * (1.x غير مُصان) الذي يُسقط الـ WebSocket بـ 1006 بعد أول إطار من الخادم — فلا
 * تصل إجابة، والواجهة تُعيد الاتصال → «متصل/غير متصل» في الثواني الأولى.
 *
 * الإصلاح: تمرير WebSocket يدوي وموثوق عبر مكتبة `ws`:
 *   1. `WebSocketServer({ noServer:true })` يستقبل الـ upgrade لمسارات الدردشة فقط.
 *   2. اتصال `ws.WebSocket` صاعد إلى الـ backend مع الحفاظ على query (?token=)
 *      والـ subprotocol.
 *   3. تمرير ثنائي الاتجاه للرسائل (نصية/ثنائية) مع نشر كود الإغلاق.
 *   4. **طابور** للرسائل التي يُرسلها العميل قبل أن يفتح الاتصال الصاعد — يحفظ
 *      «السلام عليكم» المُرسَلة فور الاتصال (سبب ضياع التحية مع http-proxy).
 *
 * `ws` متوفّرة كتبعية لـ Next؛ ومُعلَنة صراحةً في package.json.
 */

const { createServer } = require("http");
const { parse } = require("url");
const next = require("next");

// ISS-101 (D-WS-PROXY-001): تحميل `ws` بشكل دفاعي.
// المشكلة: في Codespace قائم، `npm install` لا يُعاد تلقائياً بعد git pull إذا
// كان `node_modules` موجوداً — فقد لا تُثبَّت `ws` الجديدة، و`require("ws")` يفشل
// → ينهار server.js → الواجهة تسقط كلياً. الحل: نجرّب `ws` العلوية أولاً، وإلا
// نستخدم نسخة Next المُجمَّعة (`next/dist/compiled/ws`) الموجودة دائماً مع Next.
function loadWs() {
  let mod;
  try {
    mod = require("ws");
  } catch (_e) {
    mod = require("next/dist/compiled/ws");
  }
  const WebSocketServer = mod.WebSocketServer || mod.Server;
  const WebSocket = mod.WebSocket || mod;
  return { WebSocketServer, WebSocket };
}
const { WebSocketServer, WebSocket } = loadWs();

const dev = process.env.NODE_ENV !== "production";
const hostname = process.env.HOSTNAME || "0.0.0.0";
const port = parseInt(process.env.PORT || process.env.FRONTEND_PORT || "3000", 10);

const GATEWAY_URL = process.env.API_URL || "http://127.0.0.1:8000";
const GATEWAY_WS_URL = GATEWAY_URL.replace(/^http/, "ws");
const MAX_PAYLOAD = 16 * 1024 * 1024; // 16MB

const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

const WS_PROXY_PATHS = ["/api/chat/ws", "/admin/api/chat/ws"];
const isWsProxyPath = (url) => WS_PROXY_PATHS.some((p) => url === p || url.startsWith(p + "?"));

const redact = (url) => (url || "").replace(/([?&]token=)[^&]+/, "$1[REDACTED]");

/**
 * يُنشئ اتصالاً صاعداً موثوقاً إلى الـ backend ويُمرِّر الرسائل ثنائية الاتجاه.
 * @param {WebSocket} clientWs - اتصال المتصفح (بعد handleUpgrade).
 * @param {import('http').IncomingMessage} req - طلب الـ upgrade الأصلي.
 */
function proxyToGateway(clientWs, req) {
  const url = req.url || "";
  const safe = redact(url);

  const protoHeader = req.headers["sec-websocket-protocol"];
  const subprotocols = protoHeader
    ? protoHeader.split(",").map((s) => s.trim()).filter(Boolean)
    : [];

  let upstream;
  try {
    upstream = new WebSocket(GATEWAY_WS_URL + url, subprotocols.length ? subprotocols : undefined, {
      perMessageDeflate: false,
      maxPayload: MAX_PAYLOAD,
      headers: { "x-forwarded-for": (req.socket && req.socket.remoteAddress) || "" },
    });
  } catch (err) {
    console.error("[WS Proxy] upstream connect failed:", err.message, safe);
    try {
      clientWs.close(1011, "upstream connect failed");
    } catch (_e) {
      /* noop */
    }
    return;
  }

  // طابور لرسائل العميل المُرسَلة قبل فتح الاتصال الصاعد (يحفظ التحية الأولى).
  const pending = [];
  let upstreamReady = false;

  upstream.on("open", () => {
    upstreamReady = true;
    for (const m of pending) {
      try {
        upstream.send(m.data, { binary: m.binary });
      } catch (_e) {
        /* noop */
      }
    }
    pending.length = 0;
    console.log("[WS Proxy] upstream open:", safe);
  });

  upstream.on("message", (data, isBinary) => {
    if (clientWs.readyState === WebSocket.OPEN) {
      try {
        clientWs.send(data, { binary: isBinary });
      } catch (_e) {
        /* noop */
      }
    }
  });

  upstream.on("close", (code, reason) => {
    const safeCode = code >= 1000 && code <= 4999 ? code : 1011;
    try {
      clientWs.close(safeCode, reason);
    } catch (_e) {
      try {
        clientWs.terminate();
      } catch (_e2) {
        /* noop */
      }
    }
  });

  upstream.on("error", (err) => {
    console.warn("[WS Proxy] upstream error:", err.message, safe);
    if (clientWs.readyState === WebSocket.OPEN) {
      try {
        clientWs.close(1011, "upstream error");
      } catch (_e) {
        /* noop */
      }
    }
  });

  clientWs.on("message", (data, isBinary) => {
    if (upstreamReady && upstream.readyState === WebSocket.OPEN) {
      try {
        upstream.send(data, { binary: isBinary });
      } catch (_e) {
        /* noop */
      }
    } else {
      pending.push({ data, binary: isBinary });
    }
  });

  clientWs.on("close", () => {
    try {
      upstream.close();
    } catch (_e) {
      /* noop */
    }
  });

  clientWs.on("error", () => {
    try {
      upstream.close();
    } catch (_e) {
      /* noop */
    }
  });
}

app.prepare().then(() => {
  const server = createServer(async (req, res) => {
    try {
      await handle(req, res, parse(req.url, true));
    } catch (err) {
      console.error("Error occurred handling", req.url, err);
      res.statusCode = 500;
      res.end("internal server error");
    }
  });

  // noServer mode — نملك توجيه الـ upgrade بأنفسنا.
  const wss = new WebSocketServer({ noServer: true, maxPayload: MAX_PAYLOAD });

  server.on("upgrade", (req, socket, head) => {
    const url = req.url || "";
    if (!isWsProxyPath(url)) {
      // مسارات Next الداخلية (HMR) وغيرها — لا نتدخّل فيها.
      socket.destroy();
      return;
    }
    console.log("[WS Proxy] upgrade:", redact(url), "→", GATEWAY_WS_URL);
    wss.handleUpgrade(req, socket, head, (clientWs) => {
      proxyToGateway(clientWs, req);
    });
  });

  server.listen(port, hostname, () => {
    console.log(`[Server] Ready on http://${hostname}:${port}`);
    console.log(`[Server] WS proxy (ws-lib): /api/chat/ws → ${GATEWAY_WS_URL}/api/chat/ws`);
    console.log(`[Server] Gateway: ${GATEWAY_URL}`);
  });
});
