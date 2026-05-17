#!/usr/bin/env node
/**
 * ISS-MISC-VPN / D-068 — Frontend WebSocket URL translation regression test.
 *
 * Catastrophe being prevented (2026-05-17):
 *   Frontend served at https://<codespace>-3000.app.github.dev.
 *   `getWsBase()` returned the SAME host for WS → connection landed on
 *   port 3000 (Next.js dev server, no /api/chat/ws endpoint) → handshake
 *   failed → UI stuck on "غير متصل" (offline). Users worked around it by
 *   tunneling through a VPN; the dropdown "متصل" only appeared then.
 *
 * The fix lives in `frontend/app/hooks/useAgentSocket.js`:
 *   `translateCloudHostnameToBackend(hostname)` rewrites
 *     <name>-<port>.app.github.dev          → <name>-8000.app.github.dev
 *     <name>-<port>.preview.app.github.dev  → <name>-8000.preview.app.github.dev
 *     <port>-<workspace>.gitpod.io          → 8000-<workspace>.gitpod.io
 *
 * Run:   node scripts/test_ws_url_translation.js
 * Exit:  0 if all green, 1 otherwise (use in CI).
 */

const fs = require('fs');
const path = require('path');

const SOURCE = path.join(
    __dirname,
    '..',
    'frontend',
    'app',
    'hooks',
    'useAgentSocket.js'
);

const src = fs.readFileSync(SOURCE, 'utf-8');

// Surgical extraction: pull the function + the constant out without bringing
// React along for the ride. We rely on the marker comment in the source so
// the test breaks loudly if the function is renamed or removed.
const start = src.indexOf('export const BACKEND_PORT');
const end = src.indexOf('const getWsBase');
if (start < 0 || end < 0 || end < start) {
    console.error(
        '✗ Could not locate translateCloudHostnameToBackend in source.\n' +
        '  This means the fix has been refactored away. Re-wire the WS URL\n' +
        '  derivation for cloud-forwarded hostnames or this test will keep\n' +
        '  failing.'
    );
    process.exit(2);
}

// Extract, normalise to function-scope var declarations, then eval. The
// `export` keyword and `const` are both replaced so the bindings are visible
// to the test code below (eval in nested scope can't leak `const`/`let`).
const extracted = src
    .slice(start, end)
    .replace(/export const /g, 'var ')
    .replace(/^const /gm, 'var ');
// eslint-disable-next-line no-eval
eval(extracted);

const cases = [
    // [hostname,                                          expected,                                          label]
    ['my-cs-3000.app.github.dev',                          'my-cs-8000.app.github.dev',                       'Codespaces frontend → backend (the user catastrophe)'],
    ['my-cs-5000.app.github.dev',                          'my-cs-8000.app.github.dev',                       'Codespaces port 5000 → 8000 (Replit-style)'],
    ['my-cs-3000.preview.app.github.dev',                  'my-cs-8000.preview.app.github.dev',               'Preview subdomain'],
    ['cs-with-many-hyphens-abc-def-3000.app.github.dev',   'cs-with-many-hyphens-abc-def-8000.app.github.dev','Codespace name with hyphens'],
    ['3000-workspace-id.eu-central.gitpod.io',             '8000-workspace-id.eu-central.gitpod.io',          'Gitpod URL format'],
    ['localhost',                                          null,                                              'Plain localhost — no translation'],
    ['127.0.0.1',                                          null,                                              'Localhost IP — no translation'],
    ['example.com',                                        null,                                              'Random domain — no translation'],
    ['app.github.dev',                                     null,                                              'Codespaces root domain without port — no translation'],
    ['my-cs.app.github.dev',                               null,                                              'Codespaces hostname without -port suffix'],
    [undefined,                                            null,                                              'undefined input'],
    ['',                                                   null,                                              'empty string'],
];

let pass = 0;
let fail = 0;

console.log(`BACKEND_PORT = ${BACKEND_PORT}`);
console.log();
for (const [host, expected, label] of cases) {
    const got = translateCloudHostnameToBackend(host);
    const ok = got === expected;
    const mark = ok ? '✓' : '✗';
    const left = `${mark}  ${String(host).padEnd(55)}`;
    const right = `${String(got).padEnd(48)}  [${label}]`;
    console.log(`  ${left} → ${right}`);
    if (ok) pass++; else fail++;
}
console.log();
console.log(`${pass}/${pass + fail} pass`);
process.exit(fail === 0 ? 0 : 1);
