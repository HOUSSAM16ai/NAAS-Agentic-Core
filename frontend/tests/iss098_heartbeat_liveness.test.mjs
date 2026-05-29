/**
 * ISS-098 (D-WS-FLAP-005) — Heartbeat liveness on ANY message — Regression Tests.
 *
 * كارثة متكررة (GitHub Codespaces): «لا يرد عن الأسئلة» للأسئلة الجوهرية.
 *
 * الجذر (مُثبت حياً 2026-05-29): حلقة استقبال الـ WS في الـ backend محجوبة
 * طوال `await stream_task`، فلا تقرأ ping العميل ولا تردّ بـ pong. الواجهة
 * كانت تُلغي مؤقّت الـ heartbeat (90s) عند pong فقط. سؤال جوهري → إجابة طويلة
 * (دليل حيّ: دور واحد استغرق 154.8s، 3962 delta) → يتجاوز 90s → close(1001)
 * كاذب → reconnect → الإجابة الجارية تضيع.
 *
 * إصلاح D-WS-FLAP-005 (frontend): أي رسالة واردة (delta/conversation_init/...)
 * تُلغي مؤقّت الـ heartbeat — تدفّق الـ deltas نفسه دليل قاطع على الحياة.
 * (الـ backend يُكمل ذلك بمهمة keepalive تُرسل pong كل 20s.)
 *
 * تشغيل: node frontend/tests/iss098_heartbeat_liveness.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const sourceFile = resolve(__dirname, '..', 'app', 'hooks', 'useRealtimeConnection.js');
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

console.log('ISS-098 (D-WS-FLAP-005) — frontend heartbeat liveness:');

assert('ISS-098 reference present', /ISS-098|D-WS-FLAP-005/.test(source));

// The onmessage handler must clear the heartbeat timeout BEFORE the pong-only
// branch — i.e. for any inbound message, not just pong.
const onMsgIdx = source.indexOf('ws.onmessage');
assert('ws.onmessage handler exists', onMsgIdx !== -1);

const afterOnMsg = source.slice(onMsgIdx);
const clearIdx = afterOnMsg.indexOf('clearTimeout(heartbeatTimeoutRef.current)');
const pongCheckIdx = afterOnMsg.indexOf("includes('\"type\":\"pong\"')");
assert('heartbeat timeout is cleared inside onmessage', clearIdx !== -1);
assert('pong substring check still present', pongCheckIdx !== -1);
assert(
  'liveness clearTimeout runs BEFORE the pong-only early-return',
  clearIdx !== -1 && pongCheckIdx !== -1 && clearIdx < pongCheckIdx,
);

// Guard: the pong branch must no longer be the ONLY place clearing the timeout.
// There must be a clearTimeout that is NOT guarded by a pong check immediately above it.
const universalClear =
  /if\s*\(\s*heartbeatTimeoutRef\.current\s*\)\s*\{\s*clearTimeout\(heartbeatTimeoutRef\.current\)/s;
assert('universal liveness clear block present', universalClear.test(afterOnMsg.slice(0, clearIdx + 200)));

console.log(`\nISS-098 frontend: ${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
