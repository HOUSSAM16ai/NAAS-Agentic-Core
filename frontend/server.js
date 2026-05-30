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

let _connSeq = 0;

/**
 * يُنشئ اتصالاً صاعداً موثوقاً إلى الـ backend ويُمرِّر الرسائل ثنائية الاتجاه.
 * @param {WebSocket} clientWs - اتصال المتصفح (بعد handleUpgrade).
 * @param {import('http').IncomingMessage} req - طلب الـ upgrade الأصلي.
 */
function proxyToGateway(clientWs, req) {
  const url = req.url || "";
  const safe = redact(url);
  const cid = ++_connSeq;
  // ISS-101: بصمة بناء العميل (cb) — تُثبت أي نسخة JS يُشغّلها المتصفح.
  // غياب cb أو "UNKNOWN" ⇒ المتصفح يُشغّل bundle قديماً (يحتاج إعادة تحميل/مسح كاش).
  const cbMatch = url.match(/[?&]cb=([^&]+)/);
  const clientBuild = cbMatch ? decodeURIComponent(cbMatch[1]) : "UNKNOWN(old-bundle?)";
  console.log(`[WS Proxy] #${cid} client connected (build=${clientBuild}): ${safe}`);

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
    console.error(`[WS Proxy] #${cid} upstream connect failed:`, err.message, safe);
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
  let up2cl = 0;
  let cl2up = 0;

  upstream.on("open", () => {
    upstreamReady = true;
    for (const m of pending) {
      try {
        upstream.send(m.data, { binary: m.binary });
        cl2up++;
      } catch (_e) {
        /* noop */
      }
    }
    console.log(`[WS Proxy] #${cid} upstream open (flushed ${pending.length} queued)`);
    pending.length = 0;
  });

  upstream.on("message", (data, isBinary) => {
    up2cl++;
    if (clientWs.readyState === WebSocket.OPEN) {
      try {
        clientWs.send(data, { binary: isBinary });
      } catch (e) {
        console.warn(`[WS Proxy] #${cid} client send failed:`, e.message);
      }
    }
  });

  upstream.on("close", (code, reason) => {
    const rsn = reason ? reason.toString().slice(0, 80) : "";
    console.log(`[WS Proxy] #${cid} upstream closed code=${code} reason="${rsn}" (up2cl=${up2cl} cl2up=${cl2up})`);
    const safeCode = code >= 1000 && code <= 4999 ? code : 1011;
    try {
      clientWs.close(safeCode, rsn);
    } catch (e) {
      console.warn(`[WS Proxy] #${cid} clientWs.close threw:`, e.message);
      try {
        clientWs.terminate();
      } catch (_e2) {
        /* noop */
      }
    }
  });

  upstream.on("error", (err) => {
    console.warn(`[WS Proxy] #${cid} upstream error:`, err.message, safe);
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
        cl2up++;
      } catch (e) {
        console.warn(`[WS Proxy] #${cid} upstream send failed:`, e.message);
      }
    } else {
      pending.push({ data, binary: isBinary });
      console.log(`[WS Proxy] #${cid} queued client msg (upstream not ready)`);
    }
  });

  clientWs.on("close", (code, reason) => {
    const rsn = reason ? reason.toString().slice(0, 80) : "";
    console.log(`[WS Proxy] #${cid} client closed code=${code} reason="${rsn}"`);
    try {
      upstream.close();
    } catch (_e) {
      /* noop */
    }
  });

  clientWs.on("error", (err) => {
    console.warn(`[WS Proxy] #${cid} client error:`, err.message);
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
      // ISS-101 (D-WS-KICK-DIAG): beacon تشخيصي من العميل — يطبع سبب الطرد/الحدث
      // في سجل الخادم (يُمكن للمستخدم قراءته على الجوال بلا devtools).
      if (req.method === "POST" && (req.url || "").startsWith("/__clientlog")) {
        let body = "";
        req.on("data", (c) => {
          body += c;
          if (body.length > 4096) body = body.slice(0, 4096);
        });
        req.on("end", () => {
          console.log("[CLIENT-LOG]", body.slice(0, 1000));
          res.statusCode = 204;
          res.end();
        });
        return;
      }
      await handle(req, res, parse(req.url, true));
    } catch (err) {
      console.error("Error occurred handling", req.url, err);
      res.statusCode = 500;
      res.end("internal server error");
    }
  });

  // noServer mode — نملك توجيه الـ upgrade بأنفسنا.
  const wss = new WebSocketServer({ noServer: true, maxPayload: MAX_PAYLOAD });

  // ISS-101: تشخيص — كم listener لـ 'upgrade' موجود قبل إضافة handler الخاص بنا؟
  // إن كان > 0 فهناك طرف آخر (Next/HMR) يتنافس على نفس الـ upgrade → قد يدمّر
  // الـ socket بعد مصافحتنا (سبب 1006). نُزيل أي listeners ونجعل handler الخاص
  // بنا هو الوحيد (HMR في dev قد يتعطّل — مقبول لاستقرار الدردشة).
  const preCount = server.listenerCount("upgrade");
  console.log(`[WS Proxy] upgrade listeners before ours: ${preCount}`);
  if (preCount > 0) {
    server.removeAllListeners("upgrade");
    console.log(`[WS Proxy] removed ${preCount} pre-existing upgrade listener(s) — ours is now sole`);
  }

  const upgradeHandler = (req, socket, head) => {
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
  };
  server.on("upgrade", upgradeHandler);
  // أعد تثبيت handler الخاص بنا دورياً إن أضاف Next listener لاحقاً (lazy).
  const upgradeGuard = setInterval(() => {
    const handlers = server.listeners("upgrade");
    if (handlers.length !== 1 || handlers[0] !== upgradeHandler) {
      console.log(`[WS Proxy] upgrade listeners drifted to ${handlers.length} — reasserting ours`);
      server.removeAllListeners("upgrade");
      server.on("upgrade", upgradeHandler);
    }
  }, 3000);
  if (typeof upgradeGuard.unref === "function") upgradeGuard.unref();

  server.listen(port, hostname, () => {
    console.log(`[Server] Ready on http://${hostname}:${port}`);
    console.log("[Server] WS-PROXY ISS-101 ws-lib v2 ACTIVE (instrumented)");
    console.log(`[Server] WS proxy (ws-lib): /api/chat/ws → ${GATEWAY_WS_URL}/api/chat/ws`);
    console.log(`[Server] Gateway: ${GATEWAY_URL}`);
  });
});
