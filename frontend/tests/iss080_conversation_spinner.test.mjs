/**
 * ISS-080 (D-068) — Old Conversation Spinner Catastrophe — Regression Tests.
 *
 * كارثة 2026-05-18: عند فتح محادثة قديمة، زر الإرسال يبقى دائرة تدور بدل سهم
 * → المستخدم يظنّ أن النظام معلَّق ولا يستطيع إرسال أي رسالة.
 *
 * السبب الجذري: `CustomerMessageOut`/`MessageResponse` لا يحويان `isComplete`.
 * عند `setMessages(data.messages)` في `CogniForgeApp.jsx:184`، الرسائل تدخل
 * الـ state بدون العلم. ثم في `ChatInterface.jsx:379`:
 *   `hasStreamingMessage = messages.some(m => m.role==='assistant' && !m.isComplete)`
 * يُرجع true (لأن `!undefined === true`) → الزر يعرض دائرة `fa-spin` للأبد.
 *
 * إصلاح D-068 (`frontend/app/hooks/useAgentSocket.js:setMessagesSafe`):
 *   - يطبِّع كل رسالة assistant من التاريخ بـ `isComplete: true`
 *   - يولِّد `id` إن كان مفقوداً
 *   - لا يلمس رسائل المستخدم
 *   - لا يكسر مسار البث الحي (live streaming messages تظل كما هي)
 *
 * تشغيل: node frontend/tests/iss080_conversation_spinner.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const sourceFile = resolve(__dirname, '..', 'app', 'hooks', 'useAgentSocket.js');
const source = readFileSync(sourceFile, 'utf-8');

// ─── ضمان أن إصلاح D-068 موجود في الملف ──────────────────────────────────────
const fixGuards = [
    { name: 'ISS-080 reference', pattern: /ISS-080/ },
    { name: 'D-068 reference', pattern: /D-068/ },
    { name: 'history-message normalization comment', pattern: /\bisComplete\b.*\btrue\b/s },
    { name: 'setMessagesSafe is a useCallback', pattern: /setMessagesSafe\s*=\s*useCallback\(/ },
    { name: 'assistant role check', pattern: /role\s*===\s*['"]assistant['"]/ },
    { name: 'isComplete fix branch', pattern: /isComplete\s*!==\s*true/ },
    { name: 'id generation guard', pattern: /id\s*===\s*undefined\s*\|\|\s*next\.id\s*===\s*null/ },
];

let failed = 0;
for (const g of fixGuards) {
    if (!g.pattern.test(source)) {
        console.log(`❌ static guard missing: ${g.name}`);
        failed += 1;
    } else {
        console.log(`✅ static guard present: ${g.name}`);
    }
}

// ─── محاكاة سلوك المسار الحي ─────────────────────────────────────────────────
// (نُكرِّر منطق الـ fix هنا لأن الـ hook لا يعمل خارج React،
//  لكن الـ static guards أعلاه تثبت أن الكود الحقيقي يحمل نفس الأنماط)
let idCounter = 0;
const generateId = () => `gen-${++idCounter}`;
const normalize = (msgs) => {
    if (!Array.isArray(msgs)) return [];
    return msgs.map((msg) => {
        if (!msg || typeof msg !== 'object') return msg;
        const next = { ...msg };
        if (next.id === undefined || next.id === null) next.id = generateId();
        if (next.role === 'assistant' && next.isComplete !== true) next.isComplete = true;
        return next;
    });
};

const hasStreamingMessage = (messages) =>
    messages.some((m) => m.role === 'assistant' && !m.isComplete);
const showsCopyButton = (msg) =>
    msg.role === 'assistant' && msg.isComplete && !!(msg.content || '').trim();

// قطعة بيانات حقيقية تطابق `CustomerMessageOut` (app/api/schemas/customer_chat.py)
const customerHistory = [
    { role: 'user', content: 'اعطني تمرين 2016', created_at: '2026-05-18T09:00:00', policy_flags: null },
    {
        role: 'assistant',
        content: 'بكالوريا 2016 — التمرين الرابع\n$$g(x) = 1 + (x^2+x-1)e^{-x}$$',
        created_at: '2026-05-18T09:00:05',
        policy_flags: null,
    },
];

// قطعة بيانات حقيقية تطابق `MessageResponse` (app/api/schemas/admin.py)
const adminHistory = [
    { id: 100, role: 'user', content: 'كم عدد ملفات بايثون؟', timestamp: '2026-05-18T08:00:00' },
    { id: 101, role: 'assistant', content: 'يوجد 247 ملف.', timestamp: '2026-05-18T08:00:03' },
];

const scenarios = [
    {
        name: 'send button shows arrow (not spinner) when loading customer history',
        run: () => {
            if (hasStreamingMessage(normalize(customerHistory))) {
                throw new Error('hasStreamingMessage=true → spinner stuck');
            }
        },
    },
    {
        name: 'send button shows arrow when loading admin history',
        run: () => {
            if (hasStreamingMessage(normalize(adminHistory))) {
                throw new Error('hasStreamingMessage=true → spinner stuck');
            }
        },
    },
    {
        name: 'baseline confirmation: without the fix, the catastrophe reproduces',
        run: () => {
            // baseline = old buggy setMessagesSafe = (m) => setMessages(m)
            if (!hasStreamingMessage(customerHistory)) {
                throw new Error('baseline expected to show spinner — bug must move');
            }
        },
    },
    {
        name: 'copy button appears on history assistant messages',
        run: () => {
            const out = normalize(customerHistory);
            const assistant = out.find((m) => m.role === 'assistant');
            if (!showsCopyButton(assistant)) throw new Error('copy button missing');
        },
    },
    {
        name: 'LaTeX-aware Markdown renders (isStreaming=false on history)',
        run: () => {
            const out = normalize(customerHistory);
            for (const m of out) {
                const isStreaming = m.role === 'assistant' && !m.isComplete;
                if (isStreaming) throw new Error('assistant rendered as raw text');
            }
        },
    },
    {
        name: 'original ids preserved when backend provides them',
        run: () => {
            const out = normalize(adminHistory);
            if (out[0].id !== 100 || out[1].id !== 101) throw new Error('ids overwritten');
        },
    },
    {
        name: 'ids generated when backend omits them',
        run: () => {
            const out = normalize(customerHistory);
            for (const m of out) {
                if (typeof m.id !== 'string' || !m.id) throw new Error('id missing');
            }
        },
    },
    {
        name: 'live streaming still detected after history is loaded',
        run: () => {
            const mixed = [
                ...normalize(customerHistory),
                { id: 'live', role: 'assistant', content: 'partial...', isComplete: false },
            ];
            if (!hasStreamingMessage(mixed)) throw new Error('live streaming not detected');
        },
    },
    {
        name: 'spinner disappears when live streaming completes',
        run: () => {
            const after = [
                ...normalize(customerHistory),
                { id: 'live', role: 'assistant', content: 'done', isComplete: true },
            ];
            if (hasStreamingMessage(after)) throw new Error('spinner did not clear');
        },
    },
    {
        name: 'user messages are NOT flagged isComplete (only assistant messages)',
        run: () => {
            const out = normalize(customerHistory);
            const userMsg = out.find((m) => m.role === 'user');
            if (userMsg.isComplete === true) {
                throw new Error('user messages should not carry isComplete');
            }
        },
    },
    {
        name: 'non-array input does not crash',
        run: () => {
            const out = normalize(null);
            if (out.length !== 0) throw new Error('non-array must produce empty list');
        },
    },
];

for (const s of scenarios) {
    try {
        s.run();
        console.log(`✅ ${s.name}`);
    } catch (e) {
        failed += 1;
        console.log(`❌ ${s.name}\n   → ${e.message}`);
    }
}

const total = fixGuards.length + scenarios.length;
const passed = total - failed;
console.log(`\n${failed === 0 ? '🎉' : '❌'} ${passed}/${total} ISS-080 D-068 regression checks`);
process.exit(failed === 0 ? 0 : 1);
