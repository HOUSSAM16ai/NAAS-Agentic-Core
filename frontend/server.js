/**
 * Next.js Custom Server — WebSocket Proxy
 *
 * ## لماذا هذا الملف موجود؟
 *
 * Next.js rewrites() لا تُمرِّر WebSocket upgrade headers.
 * في Codespaces: المتصفح يصل عبر *-3000.app.github.dev → Next.js
 * → WebSocket upgrade يُرفض لأن Next.js لا يُمرِّره.
 *
 * الحل: custom server يستمع على نفس port (3000/5000) ويُمرِّر:
 *   - HTTP requests → Next.js (كالمعتاد)
 *   - WebSocket /api/chat/ws → Gateway :8000/api/chat/ws
 *   - WebSocket /admin/api/chat/ws → Gateway :8000/admin/api/chat/ws
 *
 * هذا يعني المتصفح يتصل بـ *-3000.app.github.dev/api/chat/ws
 * والـ server يُمرِّره إلى Gateway (8000) داخلياً.
 *
 * D-WS-001: هذا هو الحل الصحيح لـ Codespaces WebSocket forwarding.
 */

const { createServer } = require('http');
const { parse } = require('url');
const next = require('next');
const httpProxy = require('http-proxy');

const dev = process.env.NODE_ENV !== 'production';
const hostname = process.env.HOSTNAME || '0.0.0.0';
const port = parseInt(process.env.PORT || process.env.FRONTEND_PORT || '3000', 10);

// عنوان Gateway — قابل للتهيئة
const GATEWAY_URL = process.env.API_URL || 'http://127.0.0.1:8000';
const GATEWAY_WS_URL = GATEWAY_URL.replace(/^http/, 'ws');

const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

// WebSocket proxy إلى Gateway
const wsProxy = httpProxy.createProxyServer({
    target: GATEWAY_WS_URL,
    ws: true,
    changeOrigin: true,
    // حافظ على timeout مناسب للـ WebSocket
    timeout: 0,
    proxyTimeout: 0,
});

wsProxy.on('error', (err, req, res) => {
    console.error('[WS Proxy] Error:', err.message, 'URL:', req?.url);
    // لا تُغلق الاتصال بشكل مفاجئ
    if (res && res.end && !res.headersSent) {
        res.writeHead(502, { 'Content-Type': 'text/plain' });
        res.end('WebSocket proxy error');
    }
});

wsProxy.on('proxyReqWs', (proxyReq, req) => {
    console.log('[WS Proxy] Forwarding:', req.url, '→', GATEWAY_WS_URL + req.url);
});

// WebSocket paths التي يجب تمريرها إلى Gateway
const WS_PROXY_PATHS = ['/api/chat/ws', '/admin/api/chat/ws'];

const isWsProxyPath = (url) => WS_PROXY_PATHS.some(p => url === p || url.startsWith(p + '?'));

app.prepare().then(() => {
    const server = createServer(async (req, res) => {
        try {
            const parsedUrl = parse(req.url, true);
            await handle(req, res, parsedUrl);
        } catch (err) {
            console.error('Error occurred handling', req.url, err);
            res.statusCode = 500;
            res.end('internal server error');
        }
    });

    // تمرير WebSocket upgrades
    server.on('upgrade', (req, socket, head) => {
        const url = req.url || '';

        if (isWsProxyPath(url)) {
            console.log('[WS Proxy] Upgrade:', url, '→ Gateway', GATEWAY_WS_URL);
            wsProxy.ws(req, socket, head);
        } else {
            // WebSocket غير معروف → أغلق بشكل نظيف
            console.warn('[WS Proxy] Unknown WS path:', url, '— closing');
            socket.destroy();
        }
    });

    server.listen(port, hostname, () => {
        console.log(`[Server] Ready on http://${hostname}:${port}`);
        console.log(`[Server] WebSocket proxy: /api/chat/ws → ${GATEWAY_WS_URL}/api/chat/ws`);
        console.log(`[Server] Gateway: ${GATEWAY_URL}`);
    });
});
