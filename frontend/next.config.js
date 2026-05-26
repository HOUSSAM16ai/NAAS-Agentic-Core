/** @type {import('next').NextConfig} */

// D-WS-002: Backend URL للـ HTTP rewrites (ليس WebSocket).
// WebSocket يتصل مباشرة بـ backend عبر window.location.host في wsUrl.js.
// Next.js rewrites لا تُمرِّر WebSocket upgrade headers.
const backendUrl = process.env.API_URL || 'http://127.0.0.1:8000';

const nextConfig = {
    reactStrictMode: false,
    async rewrites() {
      return [
        {
          source: '/api/:path*',
          destination: `${backendUrl}/api/:path*`,
        },
        {
            source: '/health',
            destination: `${backendUrl}/health`,
        },
        {
            source: '/admin/api/:path*',
            destination: `${backendUrl}/admin/api/:path*`,
        },
      ];
    },
    // Allow dev-mode requests from all supported hosting environments.
    // GitHub Codespaces proxies the dev server through *.app.github.dev —
    // without this, Next.js 15+ rejects those requests with ERR_HTTP_RESPONSE_CODE_FAILURE.
    // ISS-036: *.app.github.dev added to fix Codespaces proxy rejection.
    allowedDevOrigins: [
        // Replit
        '*.replit.dev',
        '*.janeway.replit.dev',
        '*.replit.app',
        // GitHub Codespaces
        '*.app.github.dev',
        '*.preview.app.github.dev',
        // Gitpod Classic
        '*.gitpod.io',
        '*.ws-eu.gitpod.io',
        '*.ws-us.gitpod.io',
        '*.ws-eu2.gitpod.io',
        // Gitpod Flex / Ona (D-WS-GITPOD-001)
        // Pattern: <PORT>--<ENV_ID>.<cluster>.gitpod.dev
        '*.gitpod.dev',
        '*.eu-central-1-01.gitpod.dev',
        '*.eu-central-1-02.gitpod.dev',
        '*.us-east-1-01.gitpod.dev',
    ],
};

module.exports = nextConfig;
