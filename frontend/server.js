/**
 * Next.js custom dev/start server with WebSocket reverse proxy.
 *
 * Why this exists (ISS-MISC-VPN, D-068 hardening 2026-05-17):
 *   The original "غير متصل" catastrophe on GitHub Codespaces had two
 *   layers of root cause:
 *     1. Frontend was building the WS URL incorrectly (fixed by
 *        `translateCloudHostnameToBackend` in useAgentSocket.js).
 *     2. Even with the URL correctly pointing at `<cs>-8000.app.github.dev`,
 *        the browser may STILL be unable to reach it because GitHub
 *        Codespaces port visibility for port 8000 can be `private` on
 *        existing Codespaces (the devcontainer.json public-default is
 *        only applied on first creation). When the WS target is private,
 *        the browser gets redirected to GitHub login and the upgrade
 *        fails silently.
 *
 *   This custom server short-circuits the entire cross-port problem:
 *   the browser only ever talks to port 3000 (frontend port). HTTP
 *   requests are handled by Next.js. WebSocket upgrades targeting
 *   `/api/chat/ws` or `/admin/api/chat/ws` are proxied to uvicorn on
 *   `localhost:8000` — same machine, internal-only, no Codespaces auth
 *   needed.
 *
 * Result: WS works on Codespaces with NO VPN regardless of port-8000
 * visibility, and we keep the cross-port fix as a defensive fallback.
 *
 * No new npm dependencies — uses only Node built-ins (http, net, url).
 */

const { createServer } = require('http');
const { parse } = require('url');
const net = require('net');
const next = require('next');

// Parse a single CLI flag (--port N, --hostname H) without pulling a CLI
// parsing library. supervisor.sh invokes `npm run dev -- --hostname 0.0.0.0
// --port 3000` (the same shape that `next dev` understood); we honor those
// flags here so the supervisor's port choice survives the transition to the
// custom server.
function getCliFlag(name) {
    const argv = process.argv;
    for (let i = 0; i < argv.length; i++) {
        if (argv[i] === `--${name}` && i + 1 < argv.length) return argv[i + 1];
        if (argv[i].startsWith(`--${name}=`)) return argv[i].slice(name.length + 3);
    }
    return undefined;
}

const dev = process.env.NODE_ENV !== 'production';
const hostname = getCliFlag('hostname') || process.env.NEXT_HOSTNAME || '0.0.0.0';
const port = parseInt(
    getCliFlag('port') ||
    process.env.PORT ||
    process.env.FRONTEND_PORT ||
    (dev ? '5000' : '5000'),
    10,
);
const backendHost = process.env.BACKEND_HOST || '127.0.0.1';
const backendPort = parseInt(process.env.BACKEND_PORT || '8000', 10);

// Paths whose WS upgrade we proxy to uvicorn. Everything else (e.g. Turbopack
// HMR or Next.js internals) is left for Next.js to handle on its own.
const PROXIED_WS_PATTERN = /^\/(?:api|admin\/api)\/chat\/ws(?:\/|\?|$)/;

const app = next({ dev, hostname, port });
const handle = app.getRequestHandler();

function proxyWebSocket(req, clientSocket, head) {
    const upstream = net.connect(backendPort, backendHost, () => {
        // Replay the upgrade request to uvicorn verbatim. The Host header
        // is PRESERVED (not rewritten) so the backend's TrustedHostMiddleware
        // still applies its allow-list — the Codespaces wildcards in
        // AppSettings.ALLOWED_HOSTS authorize the browser's Host value,
        // and anything outside them (evil.com etc.) gets rejected with 400.
        const lines = [`${req.method} ${req.url} HTTP/1.1`];
        for (let i = 0; i < req.rawHeaders.length; i += 2) {
            const name = req.rawHeaders[i];
            const value = req.rawHeaders[i + 1];
            lines.push(`${name}: ${value}`);
        }
        // Append X-Forwarded-* so the app can identify proxy hops if needed.
        lines.push(`X-Forwarded-Host: ${req.headers.host || ''}`);
        lines.push(`X-Forwarded-Proto: ${req.headers['x-forwarded-proto'] || 'http'}`);
        upstream.write(lines.join('\r\n') + '\r\n\r\n');
        if (head && head.length) upstream.write(head);

        // Bidirectional pipe — raw bytes flow both ways for the rest of
        // the WS lifetime.
        clientSocket.pipe(upstream);
        upstream.pipe(clientSocket);
    });

    const teardown = (label) => (err) => {
        if (err) {
            // Errno-typed errors (ECONNRESET, EPIPE) are normal on close
            // and shouldn't pollute logs.
            const code = err.code || '';
            if (!['ECONNRESET', 'EPIPE'].includes(code)) {
                console.warn(`[ws-proxy] ${label}: ${code || err.message}`);
            }
        }
        clientSocket.destroy();
        upstream.destroy();
    };
    upstream.on('error', teardown('upstream'));
    clientSocket.on('error', teardown('client'));
    upstream.on('end', () => clientSocket.end());
    clientSocket.on('end', () => upstream.end());
}

app.prepare().then(() => {
    // After prepare(), Next.js exposes its own upgrade handler (since v13)
    // which forwards HMR / Turbopack WS upgrades. We call it for any
    // upgrade we don't proxy ourselves.
    const upgradeHandler =
        typeof app.getUpgradeHandler === 'function' ? app.getUpgradeHandler() : null;

    const server = createServer((req, res) => {
        const parsedUrl = parse(req.url, true);
        handle(req, res, parsedUrl);
    });

    server.on('upgrade', (req, socket, head) => {
        const url = req.url || '';
        if (PROXIED_WS_PATTERN.test(url)) {
            proxyWebSocket(req, socket, head);
        } else if (upgradeHandler) {
            // Hand HMR (and any other Next.js internal WS) back to Next.js.
            upgradeHandler(req, socket, head);
        } else {
            // Older Next.js or no upgrade support — close cleanly. Next.js
            // dev HMR will reconnect on its own.
            socket.destroy();
        }
    });

    server.on('error', (err) => {
        console.error('[next-ws-proxy] server error:', err);
    });

    server.listen(port, hostname, () => {
        console.log(
            `[next-ws-proxy] ready on http://${hostname}:${port} ` +
            `(WS /api/chat/ws + /admin/api/chat/ws → ${backendHost}:${backendPort})`,
        );
    });
});
