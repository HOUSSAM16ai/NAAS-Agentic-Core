/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: false,
    async rewrites() {
      return [
        {
          source: '/api/:path*',
          destination: process.env.API_URL
            ? `${process.env.API_URL}/api/:path*`
            : 'http://127.0.0.1:8000/api/:path*',
        },
        {
            source: '/health',
            destination: process.env.API_URL
            ? `${process.env.API_URL}/health`
            : 'http://127.0.0.1:8000/health',
        },
        {
            source: '/admin/api/:path*',
            destination: process.env.API_URL
            ? `${process.env.API_URL}/admin/api/:path*`
            : 'http://127.0.0.1:8000/admin/api/:path*',
        }
      ]
    },
    // Allow dev-mode requests from all supported hosting environments.
    // GitHub Codespaces proxies the dev server through *.app.github.dev —
    // without this, Next.js 15+ rejects those requests with ERR_HTTP_RESPONSE_CODE_FAILURE.
    allowedDevOrigins: [
        // Replit
        '*.replit.dev',
        '*.janeway.replit.dev',
        '*.replit.app',
        // GitHub Codespaces
        '*.app.github.dev',
        '*.preview.app.github.dev',
        // Gitpod / Ona
        '*.gitpod.io',
        '*.ws-eu*.gitpod.io',
    ],
};

module.exports = nextConfig;
