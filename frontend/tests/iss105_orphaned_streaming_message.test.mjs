/**
 * ISS-105 (D-WS-ORPHAN-001) — Orphaned Streaming Message — Regression Tests.
 *
 * كارثة 2026-06-01 (شاشات المستخدم): مؤشّر أزرق نابض عالق في *منتصف* المحادثة +
 * زر الإرسال يدور بدون توقف إطلاقاً + LaTeX خام يختفي فقط عند الدخول/الخروج.
 *
 * السبب الجذري: حدث `ui_component` (مثل BKT المُبثّ بالتوازي كـ background task، أو
 * full_exercise_story / math_explanation_card) قد يصل في *منتصف* بثّ النص — بين
 * delta و delta. معالج `ui_component` كان يُلحِق فقاعة مكوّن جديدة (isComplete:true)
 * دون إنهاء فقاعة النص الجارية قبله، فتبقى تلك الفقاعة يتيمة بـ isComplete:false:
 *   - ChatInterface.jsx:387 `hasStreamingMessage` = messages.some(!isComplete) → true
 *     → زر الإرسال يدور أبداً (fa-circle-notch fa-spin).
 *   - ChatInterface.jsx:270 الفقاعة اليتيمة isStreaming → مؤشّر أزرق نابض في المنتصف.
 *   - ChatInterface.jsx:206 فرع streaming-raw → LaTeX خام (يُحلّ فقط عبر إعادة
 *     التحميل D-068 setMessagesSafe الذي يفرض isComplete:true).
 *
 * الإصلاح (D-WS-ORPHAN-001):
 *   1. معالج `ui_component` يُنهي أي رسالة نص جارية قبل إلحاق فقاعة المكوّن.
 *   2. دفاع عميق: المعالجات النهائية (complete/assistant_final/error/assistant_error)
 *      تكنس كل رسالة مساعد عالقة (finalizeStaleAssistantMessages) لا الأخيرة فقط.
 *
 * تشغيل: node frontend/tests/iss105_orphaned_streaming_message.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const hookFile = resolve(__dirname, '..', 'app', 'hooks', 'useAgentSocket.js');
const source = readFileSync(hookFile, 'utf-8');

let failed = 0;

const sliceHandler = (key) => {
    const start = source.indexOf(`if (type === '${key}')`);
    if (start === -1) return '';
    const rest = source.slice(start + 8);
    const next = rest.indexOf('else if (type ===');
    return next === -1 ? rest : rest.slice(0, next);
};

const uiBlock = sliceHandler('ui_component');
const completeBlock = sliceHandler('complete');
const finalBlock = sliceHandler('assistant_final');
const errorBlock = sliceHandler('error');
const assistantErrorBlock = sliceHandler('assistant_error');

// ─── ضمانات ثابتة: الإصلاح موجود في المصدر الحقيقي ───────────────────────────
const fixGuards = [
    { name: 'ISS-105 reference present', pattern: /ISS-105/, hay: source },
    { name: 'helper finalizeStaleAssistantMessages defined', pattern: /const finalizeStaleAssistantMessages\s*=/, hay: source },
    { name: 'helper finalizes only !isComplete assistant (preserves isError)', pattern: /role === 'assistant' && !msg\.isComplete/, hay: source },
    { name: 'ui_component finalizes prior streaming msg before appending', pattern: /finalizeStaleAssistantMessages\(prev\)/, hay: uiBlock },
    { name: 'ui_component still appends component bubble (isComplete:true)', pattern: /isComplete:\s*true,\s*\n?\s*uiComponent:/, hay: uiBlock },
    { name: 'complete handler sweeps stale messages', pattern: /finalizeStaleAssistantMessages\(prev\)/, hay: completeBlock },
    { name: 'assistant_final handler sweeps stale messages', pattern: /finalizeStaleAssistantMessages\(next\)/, hay: finalBlock },
    { name: 'error handler sweeps stale messages', pattern: /finalizeStaleAssistantMessages\(next\)/, hay: errorBlock },
    { name: 'assistant_error handler sweeps stale messages', pattern: /finalizeStaleAssistantMessages\(next\)/, hay: assistantErrorBlock },
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
const mergeAssistantContent = (existingContent, incomingContent) => {
    const current = typeof existingContent === 'string' ? existingContent : '';
    const incoming = typeof incomingContent === 'string' ? incomingContent : '';
    if (!incoming) return current;
    if (!current) return incoming;
    if (incoming.startsWith(current)) return incoming;
    if (current.endsWith(incoming)) return current;
    return `${current}${incoming}`;
};

// finalizeStaleAssistantMessages (useAgentSocket.js, verbatim)
const finalizeStaleAssistantMessages = (messages) => {
    if (!Array.isArray(messages)) return messages;
    let mutated = false;
    const next = messages.map((msg) => {
        if (msg && msg.role === 'assistant' && !msg.isComplete) {
            mutated = true;
            return { ...msg, isComplete: true };
        }
        return msg;
    });
    return mutated ? next : messages;
};

let idc = 0;
const generateId = () => `m${++idc}`;

// reducer: mode 'buggy' (قبل) vs 'fixed' (بعد) — يطابق المصدر بدقة
function makeReducer(mode) {
    const fixed = mode === 'fixed';
    return (messages, ev) => {
        const { type, payload } = ev;
        if (type === 'ui_component') {
            const component = payload?.component;
            if (typeof component !== 'string' || !component) return messages;
            const bubble = {
                id: generateId(),
                role: 'assistant',
                content: '',
                isComplete: true,
                uiComponent: {
                    component,
                    props: payload?.props && typeof payload.props === 'object' ? payload.props : {},
                    fallbackText: String(payload?.fallback_text || 'تعذّر عرض المكوّن.'),
                },
            };
            const base = fixed ? finalizeStaleAssistantMessages(messages) : messages;
            return [...base, bubble];
        }
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
            if (fixed) return finalizeStaleAssistantMessages(messages);
            const last = messages[messages.length - 1];
            if (last && last.role === 'assistant') return [...messages.slice(0, -1), { ...last, isComplete: true }];
            return messages;
        }
        if (type === 'assistant_final') {
            const content = payload?.content || '';
            const uiComponent = payload?.ui_component || null;
            const last = messages[messages.length - 1];
            let next;
            if (last && last.role === 'assistant' && !last.isComplete && !last.isError) {
                const nc = content ? mergeAssistantContent(last.content, content) : last.content;
                next = [...messages.slice(0, -1), { ...last, content: nc, isComplete: true, uiComponent }];
            } else if (content) {
                next = [...messages, { id: generateId(), role: 'assistant', content, isComplete: true, uiComponent }];
            } else if (last && last.role === 'assistant' && !last.isComplete) {
                next = [...messages.slice(0, -1), { ...last, isComplete: true, uiComponent }];
            } else {
                next = messages;
            }
            return fixed ? finalizeStaleAssistantMessages(next) : next;
        }
        if (type === 'error' || type === 'assistant_error') {
            const last = messages[messages.length - 1];
            let next = messages;
            if (last && last.role === 'assistant' && !last.isComplete) {
                next = [...messages.slice(0, -1), { ...last, isComplete: true, isError: true }];
            }
            return fixed ? finalizeStaleAssistantMessages(next) : next;
        }
        return messages;
    };
}

const hasStreamingMessage = (m) => m.some((x) => x.role === 'assistant' && !x.isComplete);
const isStreamingRender = (msg) => msg.role === 'assistant' && !msg.isComplete; // ChatInterface.jsx:270

// تسلسل الخادم الحقيقي: نص تمرين → BKT ui_component (متوازٍ، في المنتصف) → نص الإجابة → assistant_final
const EXERCISE_BKT_ANSWER = [
    { type: 'assistant_delta', payload: { content: 'الدالة \\(g\\) المعرَّفة على \\(\\mathbb{R}\\):\n', request_id: 'r1' } },
    { type: 'assistant_delta', payload: { content: '$$g(x) = 1 + (x^2 + x - 1)e^{-x}$$', request_id: 'r1' } },
    { type: 'ui_component', payload: { component: 'bkt_hint_display', props: { concept_id: 'general' }, fallback_text: 'تتبّع المعرفة', request_id: 'r1' } },
    { type: 'assistant_delta', payload: { content: 'ومنه \\(g\'(x) \\le 0\\) ومتناقصة.', request_id: 'r1' } },
    { type: 'assistant_final', payload: { content: '', request_id: 'r1' } },
];

// تسلسل: نص ثم math_explanation_card ثم لا مزيد من نص، ينتهي بـ complete
const TEXT_THEN_CARD_COMPLETE = [
    { type: 'assistant_delta', payload: { content: 'إليك الشرح:', request_id: 'r2' } },
    { type: 'ui_component', payload: { component: 'math_explanation_card', props: { math_type: 'integral' }, fallback_text: 'بطاقة شرح', request_id: 'r2' } },
    { type: 'complete', payload: { request_id: 'r2' } },
];

// تسلسل ينتهي بـ error بعد ui_component يتيم
const TEXT_THEN_CARD_ERROR = [
    { type: 'assistant_delta', payload: { content: 'تمرين \\(H(x) = (ax^2+bx+c)e^{-x}\\)', request_id: 'r3' } },
    { type: 'ui_component', payload: { component: 'full_exercise_story', props: {}, fallback_text: 'قصة', request_id: 'r3' } },
    { type: 'error', payload: { details: 'persistence failed', request_id: 'r3' } },
];

function play(mode, seq) {
    const reduce = makeReducer(mode);
    let msgs = [];
    for (const ev of seq) msgs = reduce(msgs, ev);
    return msgs;
}

const scenarios = [
    {
        name: 'BUGGY baseline: ui_component mid-stream orphans prior text → spinner stuck',
        run: () => {
            const msgs = play('buggy', EXERCISE_BKT_ANSWER);
            if (!hasStreamingMessage(msgs)) throw new Error('baseline must reproduce the orphaned-message hang');
            // الفقاعة العالقة في المنتصف (ليست الأخيرة)
            const orphan = msgs.find((m) => m.role === 'assistant' && !m.isComplete);
            if (!orphan || !/g\(x\)/.test(orphan.content)) throw new Error('orphan must be the mid-conversation exercise text');
        },
    },
    {
        name: 'FIXED: ui_component finalizes prior text → no streaming message remains',
        run: () => {
            const msgs = play('fixed', EXERCISE_BKT_ANSWER);
            if (hasStreamingMessage(msgs)) throw new Error('spinner still stuck — orphan not finalized');
        },
    },
    {
        name: 'FIXED: every assistant bubble is finalized (no mid-conversation blue cursor)',
        run: () => {
            const msgs = play('fixed', EXERCISE_BKT_ANSWER);
            const stuck = msgs.filter((m) => isStreamingRender(m));
            if (stuck.length !== 0) throw new Error(`${stuck.length} bubble(s) still rendering streaming-raw (cursor)`);
        },
    },
    {
        name: 'FIXED: BKT component bubble preserved + ordered before the answer text',
        run: () => {
            const msgs = play('fixed', EXERCISE_BKT_ANSWER);
            const card = msgs.find((m) => m.uiComponent?.component === 'bkt_hint_display');
            if (!card) throw new Error('component bubble lost');
            // الترتيب: نص التمرين (مُنهى) → بطاقة BKT → نص الإجابة (مُنهى)
            const idxExercise = msgs.findIndex((m) => /g\(x\)/.test(m.content || ''));
            const idxCard = msgs.indexOf(card);
            const idxAnswer = msgs.findIndex((m) => /متناقصة/.test(m.content || ''));
            if (!(idxExercise < idxCard && idxCard < idxAnswer)) throw new Error('ordering broken');
        },
    },
    {
        name: 'BUGGY baseline: text → card → complete leaves orphan (complete only finalized last=card)',
        run: () => {
            const msgs = play('buggy', TEXT_THEN_CARD_COMPLETE);
            if (!hasStreamingMessage(msgs)) throw new Error('baseline must reproduce orphan with complete frame');
        },
    },
    {
        name: 'FIXED: text → card → complete sweep finalizes the orphaned text',
        run: () => {
            const msgs = play('fixed', TEXT_THEN_CARD_COMPLETE);
            if (hasStreamingMessage(msgs)) throw new Error('complete sweep did not finalize orphan');
        },
    },
    {
        name: 'FIXED: text → card → error finalizes orphan WITHOUT marking it isError',
        run: () => {
            const msgs = play('fixed', TEXT_THEN_CARD_ERROR);
            if (hasStreamingMessage(msgs)) throw new Error('error sweep did not finalize orphan');
            const textMsg = msgs.find((m) => /H\(x\)/.test(m.content || ''));
            if (!textMsg || textMsg.isComplete !== true) throw new Error('orphan text not finalized');
            if (textMsg.isError === true) throw new Error('orphan text wrongly marked isError (only current-turn last may be isError)');
        },
    },
    {
        name: 'FIXED: a normal single-bubble turn is unaffected (no spurious changes)',
        run: () => {
            const seq = [
                { type: 'assistant_delta', payload: { content: 'مرحبا', request_id: 'r4' } },
                { type: 'assistant_final', payload: { content: '', request_id: 'r4' } },
            ];
            const msgs = play('fixed', seq);
            if (msgs.length !== 1) throw new Error('unexpected message count');
            if (!msgs[0].isComplete) throw new Error('single bubble not finalized');
        },
    },
];

for (const s of scenarios) {
    try {
        s.run();
        console.log(`✅ ${s.name}`);
    } catch (err) {
        console.log(`❌ ${s.name}: ${err.message}`);
        failed += 1;
    }
}

if (failed > 0) {
    console.log(`\n💥 ISS-105: ${failed} check(s) failed`);
    process.exit(1);
}
console.log('\n🎉 ISS-105 D-WS-ORPHAN-001 — all regression checks passed');
