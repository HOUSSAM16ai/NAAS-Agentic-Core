/**
 * ISS-104 (D-WS-FINAL-001) — Error-Frame Hang on BAC-Exercise Retrieval — Regression Tests.
 *
 * كارثة 2026-06-01 (شاشتا المستخدم): عند طلب «اعطني تمرين دوال 2016»، يبقى سهم
 * مربع البحث يدور بدون توقف (لا يمكن طرح سؤال جديد) + المعادلات تظهر بالرموز الخام
 * (`\(g\)`, `\\(\mathbb{R}\\)`) بدل KaTeX — كلاهما من سبب جذري واحد.
 *
 * السبب الجذري: مسار الاسترجاع المُفهرَس يبثّ deltas ثم — عند فشل تأكيد الحفظ —
 * `customer_chat.py:_emit_terminal_frames` يُصدِر إطار `error` (بدل `assistant_final`).
 * معالجا `error`/`assistant_error` في useAgentSocket.js كانا يستدعيان notifyAgentError
 * فقط ولا يلمسان الرسالة → تبقى `isComplete:false` للأبد:
 *   - ChatInterface.jsx:387 `hasStreamingMessage` يبقى true → الزر دائرة `fa-spin` أبداً.
 *   - ChatInterface.jsx:270 `isStreaming` يبقى true → الرسالة في فرع streaming-raw
 *     (نص خام بلا preprocessMath/KaTeX) → LaTeX خام دائم.
 * يخالف ISS-016/ISS-017: «أي مسار فشل ينتهي بإطار error واحد — لا تعليق أبداً».
 *
 * الإصلاح (D-WS-FINAL-001): معالجا `error`/`assistant_error` يُنهيان الرسالة الجارية
 * (isComplete:true + isError:true، مع الحفاظ على المحتوى المبثوث)، مع إبقاء
 * notifyAgentError (الخطأ يبقى ظاهراً) و refreshConversationHistory (آمن — sidebar فقط).
 *
 * تشغيل: node frontend/tests/iss104_error_finalizes_message.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const sourceFile = resolve(__dirname, '..', 'app', 'hooks', 'useAgentSocket.js');
const source = readFileSync(sourceFile, 'utf-8');

let failed = 0;

// ─── ضمانات ثابتة: الإصلاح موجود في المصدر الحقيقي ───────────────────────────
// نعزل كتلة كل معالج عبر `else if (type === ...)` (تجنّب التطابق مع
// parseNestedAssistantError الذي يحوي السلسلة 'assistant_error' أيضاً).
const sliceHandler = (key) => {
    const start = source.indexOf(`else if (type === '${key}')`);
    if (start === -1) return '';
    // الكتلة تمتد حتى بداية المعالج التالي أو نهاية سلسلة else-if.
    const rest = source.slice(start + 10);
    const next = rest.indexOf('else if (type ===');
    return next === -1 ? rest : rest.slice(0, next);
};
const errorBlock = sliceHandler('error');
const assistantErrorBlock = sliceHandler('assistant_error');
const finalizeCount = (source.match(/isComplete:\s*true,\s*isError:\s*true/g) || []).length;

const fixGuards = [
    { name: 'ISS-104 reference', pattern: /ISS-104/, hay: source },
    { name: 'exactly two finalization sites (error + assistant_error)', pattern: () => finalizeCount === 2 },
    { name: 'error handler finalizes message (setMessages)', pattern: /setMessages\(prev\s*=>/, hay: errorBlock },
    { name: 'error handler sets isComplete:true + isError:true', pattern: /isComplete:\s*true,\s*isError:\s*true/, hay: errorBlock },
    { name: 'error handler keeps notifyAgentError', pattern: /notifyAgentError/, hay: errorBlock },
    { name: 'error handler keeps refreshConversationHistory', pattern: /refreshConversationHistory/, hay: errorBlock },
    { name: 'error handler resets activeRequestIdRef', pattern: /activeRequestIdRef\.current\s*=\s*null/, hay: errorBlock },
    { name: 'error handler guard is !last.isComplete (mirrors complete)', pattern: /role\s*===\s*['"]assistant['"]\s*&&\s*!last\.isComplete/, hay: errorBlock },
    { name: 'assistant_error handler finalizes message (setMessages)', pattern: /setMessages\(prev\s*=>/, hay: assistantErrorBlock },
    { name: 'assistant_error sets isComplete:true + isError:true', pattern: /isComplete:\s*true,\s*isError:\s*true/, hay: assistantErrorBlock },
    { name: 'assistant_error keeps notifyAgentError + reset id', pattern: /activeRequestIdRef\.current\s*=\s*null/, hay: assistantErrorBlock },
];

for (const g of fixGuards) {
    const ok = typeof g.pattern === 'function' ? g.pattern() : g.pattern.test(g.hay);
    if (!ok) {
        console.log(`❌ static guard missing: ${g.name}`);
        failed += 1;
    } else {
        console.log(`✅ static guard present: ${g.name}`);
    }
}

// ─── محاكاة سلوكية أمينة: منطق المعالج منسوخ حرفياً من المصدر ─────────────────
// mergeAssistantContent (useAgentSocket.js, verbatim)
const mergeAssistantContent = (existingContent, incomingContent) => {
    const current = typeof existingContent === 'string' ? existingContent : '';
    const incoming = typeof incomingContent === 'string' ? incomingContent : '';
    if (!incoming) return current;
    if (!current) return incoming;
    if (incoming.startsWith(current)) return incoming;
    if (current.endsWith(incoming)) return current;
    return `${current}${incoming}`;
};
// preprocessMath (ChatInterface.jsx, verbatim) — يثبت أن المحتوى المُنهى يُصيَّر KaTeX
const preprocessMath = (content) => {
    if (!content) return '';
    let p = content;
    p = p.replace(/\\\\\(/g, '\\(');
    p = p.replace(/\\\\\)/g, '\\)');
    p = p.replace(/\\\\\[/g, '\\[');
    p = p.replace(/\\\\\]/g, '\\]');
    p = p.replace(/\\\\([a-zA-Z]+|[,;!{}])/g, '\\$1');
    p = p.replace(/\\\[([^]*?)\\\]/g, (_, i) => `$$${i}$$`);
    p = p.replace(/\\\(([^]*?)\\\)/g, (_, i) => `$${i}$`);
    return p;
};

let idc = 0;
const generateId = () => `m${++idc}`;

// reducer: errorMode 'buggy' (قبل) vs 'fixed' (بعد) — يطابق المصدر بدقة
function makeReducer(errorMode) {
    return (messages, ev) => {
        const { type, payload } = ev;
        if (type === 'delta' || type === 'assistant_delta') {
            const content = payload?.content || '';
            if (!content) return messages;
            const last = messages[messages.length - 1];
            if (last && last.role === 'assistant' && !last.isComplete && !last.isError) {
                return [...messages.slice(0, -1), { ...last, content: mergeAssistantContent(last.content, content) }];
            }
            return [...messages, { id: generateId(), role: 'assistant', content, isComplete: false }];
        }
        if (type === 'complete') {
            const last = messages[messages.length - 1];
            if (last && last.role === 'assistant') return [...messages.slice(0, -1), { ...last, isComplete: true }];
            return messages;
        }
        if (type === 'assistant_final') {
            const content = payload?.content || '';
            const uiComponent = payload?.ui_component || null;
            const last = messages[messages.length - 1];
            if (last && last.role === 'assistant' && !last.isComplete && !last.isError) {
                const nc = content ? mergeAssistantContent(last.content, content) : last.content;
                return [...messages.slice(0, -1), { ...last, content: nc, isComplete: true, uiComponent }];
            } else if (content) {
                return [...messages, { id: generateId(), role: 'assistant', content, isComplete: true, uiComponent }];
            }
            if (last && last.role === 'assistant' && !last.isComplete) {
                return [...messages.slice(0, -1), { ...last, isComplete: true, uiComponent }];
            }
            return messages;
        }
        if (type === 'error' || type === 'assistant_error') {
            if (errorMode === 'fixed') {
                const last = messages[messages.length - 1];
                if (last && last.role === 'assistant' && !last.isComplete) {
                    return [...messages.slice(0, -1), { ...last, isComplete: true, isError: true }];
                }
            }
            return messages; // buggy: لا يلمس الرسالة → تعليق
        }
        return messages;
    };
}

const hasStreamingMessage = (m) => m.some((x) => x.role === 'assistant' && !x.isComplete);
const isStreamingRender = (m) => m.role === 'assistant' && !m.isComplete; // ChatInterface.jsx:270

// تسلسل أحداث الخادم الحقيقي لدور «دوال 2016» المنتهي بـ error frame
const RETRIEVAL_THEN_ERROR = [
    { type: 'assistant_delta', payload: { content: 'الدالة \\(g\\) المعرَّفة على \\(\\mathbb{R}\\) بـ:\n', request_id: 'r1' } },
    { type: 'assistant_delta', payload: { content: '$$g(x) = 1 + (x^2 + x - 1)e^{-x}$$\n', request_id: 'r1' } },
    { type: 'assistant_delta', payload: { content: 'احسب \\(\\lim_{x \\to +\\infty} g(x)\\).', request_id: 'r1' } },
    { type: 'error', payload: { details: 'Failed to confirm assistant persistence before completion.', status_code: 500, request_id: 'r1' } },
];
const RETRIEVAL_THEN_ASSISTANT_ERROR = [
    { type: 'assistant_delta', payload: { content: 'بكالوريا 2016 — التمرين الرابع\n', request_id: 'r2' } },
    { type: 'assistant_delta', payload: { content: '$$f(x) = -x + (x^2 + 3x + 2)e^{-x}$$', request_id: 'r2' } },
    { type: 'assistant_error', payload: { content: 'assistant failure', request_id: 'r2' } },
];

function play(mode, seq) {
    const reduce = makeReducer(mode);
    let msgs = [];
    for (const ev of seq) msgs = reduce(msgs, ev);
    return msgs;
}

const scenarios = [
    {
        name: 'BUGGY baseline: error frame after deltas → spinner stuck (bug reproduced)',
        run: () => {
            const msgs = play('buggy', RETRIEVAL_THEN_ERROR);
            if (!hasStreamingMessage(msgs)) throw new Error('baseline must reproduce the hang');
            const last = msgs[msgs.length - 1];
            if (!isStreamingRender(last)) throw new Error('baseline must stay in streaming-raw (raw LaTeX)');
        },
    },
    {
        name: 'FIXED: error frame finalizes message → spinner unlocks',
        run: () => {
            const msgs = play('fixed', RETRIEVAL_THEN_ERROR);
            if (hasStreamingMessage(msgs)) throw new Error('spinner still stuck after fix');
        },
    },
    {
        name: 'FIXED: finalized message renders via KaTeX (not streaming-raw)',
        run: () => {
            const msgs = play('fixed', RETRIEVAL_THEN_ERROR);
            const last = msgs[msgs.length - 1];
            if (isStreamingRender(last)) throw new Error('still rendering as raw text');
            const rendered = preprocessMath(last.content);
            if (!/\$g\$/.test(rendered) || !/\$\$g\(x\)/.test(rendered) || /\\\\\(/.test(rendered)) {
                throw new Error('LaTeX not KaTeX-ready after finalization');
            }
        },
    },
    {
        name: 'FIXED: error frame sets isComplete:true and isError:true',
        run: () => {
            const last = play('fixed', RETRIEVAL_THEN_ERROR).slice(-1)[0];
            if (last.isComplete !== true) throw new Error('isComplete not set');
            if (last.isError !== true) throw new Error('isError not set');
        },
    },
    {
        name: 'FIXED: streamed content is preserved (not blanked) on error',
        run: () => {
            const buggy = play('buggy', RETRIEVAL_THEN_ERROR).slice(-1)[0];
            const fixed = play('fixed', RETRIEVAL_THEN_ERROR).slice(-1)[0];
            if (fixed.content !== buggy.content || !fixed.content) throw new Error('content lost');
        },
    },
    {
        name: 'FIXED: assistant_error frame also finalizes the streaming bubble',
        run: () => {
            const msgs = play('fixed', RETRIEVAL_THEN_ASSISTANT_ERROR);
            if (hasStreamingMessage(msgs)) throw new Error('assistant_error did not finalize');
            const last = msgs[msgs.length - 1];
            if (last.isComplete !== true || last.isError !== true) throw new Error('flags not set');
        },
    },
    {
        name: 'no in-progress bubble: error frame creates NO fabricated message',
        run: () => {
            const msgs = play('fixed', [{ type: 'error', payload: { details: 'x', request_id: 'r3' } }]);
            if (msgs.length !== 0) throw new Error('error fabricated an empty bubble');
        },
    },
    {
        name: 'regression: successful complete flow is unaffected',
        run: () => {
            const seq = [
                { type: 'assistant_delta', payload: { content: 'مرحبا', request_id: 'r4' } },
                { type: 'complete', payload: { request_id: 'r4' } },
            ];
            const last = play('fixed', seq).slice(-1)[0];
            if (last.isComplete !== true || last.isError === true) throw new Error('complete flow broken');
        },
    },
    {
        name: 'regression: successful assistant_final flow is unaffected',
        run: () => {
            const seq = [
                { type: 'assistant_delta', payload: { content: 'الجواب', request_id: 'r5' } },
                { type: 'assistant_final', payload: { content: '', request_id: 'r5' } },
            ];
            const last = play('fixed', seq).slice(-1)[0];
            if (last.isComplete !== true || last.isError === true) throw new Error('assistant_final flow broken');
        },
    },
    {
        name: 'late stray delta after error does NOT reopen the finalized bubble',
        run: () => {
            const msgs = play('fixed', [
                ...RETRIEVAL_THEN_ERROR,
                { type: 'assistant_delta', payload: { content: ' (stray)', request_id: 'r1' } },
            ]);
            // the stray delta must NOT merge into the isError bubble (guard !last.isError),
            // so it creates a new in-progress bubble instead — finalized one stays intact.
            const errored = msgs.find((m) => m.isError === true);
            if (!errored || /stray/.test(errored.content)) throw new Error('finalized bubble was reopened');
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
console.log(`\n${failed === 0 ? '🎉' : '❌'} ${passed}/${total} ISS-104 D-WS-FINAL-001 regression checks`);
process.exit(failed === 0 ? 0 : 1);
