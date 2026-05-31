/**
 * ISS-102 (D-WS-PROXY-004) — Double WebSocket Handshake — Regression Tests.
 *
 * الكارثة (مُثبتة حياً byte-level، 2026-05-31): Next 16 يُعيد تسجيل
 * listener('upgrade') خاصاً به بعد `removeAllListeners` → listener-ان لكل ترقية
 * WS → كلاهما يكتب handshake 101 على نفس socket العميل → الإطار الثاني يصل خاماً
 * («HTTP/1.1 101…» نص) فيُقرأ كإطار RSV1 تالف → «RSV1 must be clear» → موت
 * الاتصال بعد session_ready مباشرة → لا تصل أي إجابة عبر :5000 (المباشر :8000 سليم).
 *
 * الإصلاح: server.js يملك listener('upgrade') وحيداً، ويعترض أي تسجيل لاحق
 * (on/addListener/prependListener) ويلتقطه كـ delegate لـ HMR بدل تركه موازياً.
 * + proxy نظيف: perMessageDeflate:false + compress:false.
 *
 * نمط الاختبار: فحص مصدر server.js (مطابق لـ iss098_heartbeat_liveness.test.mjs).
 * تشغيل: node frontend/tests/iss102_ws_double_handshake.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const sourceFile = resolve(__dirname, '..', 'server.js');
const source = readFileSync(sourceFile, 'utf-8');

let passed = 0;
let failed = 0;
const assert = (name, cond) => {
  if (cond) {
    passed += 1;
    console.log(`  ✅ ${name}`);
  } else {
    failed += 1;
    console.error(`  ❌ ${name}`);
  }
};

console.log('ISS-102 (D-WS-PROXY-004) — server.js single upgrade listener:');

assert('ISS-102 / D-WS-PROXY-004 reference present', /ISS-102|D-WS-PROXY-004/.test(source));

// ── Single-listener trap ────────────────────────────────────────────────────
assert('captures original on() via server.on.bind(server)', /_origAddListener\s*=\s*server\.on\.bind\(server\)/.test(source));
assert('_trapUpgrade defined', /_trapUpgrade\s*=\s*\(\s*event\s*,\s*listener\s*\)\s*=>/.test(source));
assert(
  'trap captures "upgrade" as delegate (not a parallel listener)',
  /if\s*\(\s*event\s*===\s*["']upgrade["']\s*\)\s*\{\s*\n?\s*(?:\/\/[^\n]*\n\s*)*delegatedNextUpgrade\s*=\s*listener/.test(source),
);

// All three add-listener entry points must be re-routed through the trap.
for (const m of ['on', 'addListener', 'prependListener']) {
  assert(`server.${m} reassigned to _trapUpgrade`, new RegExp(`server\\.${m}\\s*=\\s*_trapUpgrade`).test(source));
}

// The ONE real listener must be registered through the captured original, never
// through the trapped server.on(...) (which would be captured, not attached).
assert('removeAllListeners("upgrade") still called', /removeAllListeners\(\s*["']upgrade["']\s*\)/.test(source));
assert('real listener registered via _origAddListener("upgrade", ...)', /_origAddListener\(\s*["']upgrade["']\s*,/.test(source));
assert(
  'real listener NOT registered via bare server.on("upgrade", ...)',
  !/server\.on\(\s*["']upgrade["']\s*,/.test(source),
);

// ── HMR delegation preserved (no reload loop) ───────────────────────────────
assert('chat paths routed to wss.handleUpgrade', /isWsProxyPath\(url\)[\s\S]{0,200}wss\.handleUpgrade/.test(source));
assert('non-chat upgrades delegated to delegatedNextUpgrade (HMR)', /delegatedNextUpgrade\(\s*req\s*,\s*socket\s*,\s*head\s*\)/.test(source));

// ── Byte-clean proxy (no compression negotiation on the client-facing side) ──
assert('WebSocketServer disables perMessageDeflate', /new\s+WebSocketServer\(\s*\{[\s\S]*?perMessageDeflate:\s*false[\s\S]*?\}\s*\)/.test(source));
assert('relayed clientWs.send forces compress:false', /clientWs\.send\(\s*data\s*,\s*\{[^}]*compress:\s*false[^}]*\}\s*\)/.test(source));

// ── Anti-regression: never revert to http-proxy for WebSocket ───────────────
assert('does not use http-proxy for WS', !/require\(\s*["']http-proxy["']\s*\)/.test(source));

console.log(`\nISS-102 server.js: ${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
