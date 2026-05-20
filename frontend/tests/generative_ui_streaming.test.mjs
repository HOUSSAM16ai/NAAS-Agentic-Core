/**
 * Generative UI Streaming — Frontend Regression Tests.
 *
 * يثبت أن عقد بثّ مكوّنات الواجهة التوليدية (ui_component) مُطبَّق على الواجهة:
 *   1. static guards — وجود الكود الصحيح في الملفات الفعلية.
 *   2. behavioral — محاكاة reducer الخاص بـ useAgentSocket لحدث ui_component.
 *   3. fault-tolerance — محاكاة منطق Error Boundary / السجل (registry).
 *
 * الـ hooks/components لا تعمل خارج React، لذا نُحاكي المنطق هنا، والـ static
 * guards تثبت أن نفس الأنماط موجودة في الكود الحقيقي (نفس نهج iss080 test).
 *
 * تشغيل: node frontend/tests/generative_ui_streaming.test.mjs
 */

import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, '..', 'app');

const read = (rel) => readFileSync(resolve(root, rel), 'utf-8');

let failed = 0;
const check = (name, ok) => {
    if (ok) {
        console.log(`✅ ${name}`);
    } else {
        console.log(`❌ ${name}`);
        failed += 1;
    }
};

// ─── 1. الملفات موجودة ─────────────────────────────────────────────────────────
const files = {
    boundary: 'components/generative/GenerativeUIErrorBoundary.jsx',
    renderer: 'components/generative/GenerativeUIRenderer.jsx',
    tree: 'components/generative/ProbabilityTree.jsx',
    socket: 'hooks/useAgentSocket.js',
    chat: 'components/ChatInterface.jsx',
};
for (const [k, rel] of Object.entries(files)) {
    check(`file exists: ${rel}`, existsSync(resolve(root, rel)));
}

// ─── 2. static guards ──────────────────────────────────────────────────────────
const socketSrc = read(files.socket);
check('useAgentSocket handles ui_component', /type\s*===\s*['"]ui_component['"]/.test(socketSrc));
check('useAgentSocket attaches uiComponent to message', /uiComponent\s*:/.test(socketSrc));
check('useAgentSocket reads fallback_text', /fallback_text/.test(socketSrc));

const boundarySrc = read(files.boundary);
check('boundary has getDerivedStateFromError', /getDerivedStateFromError/.test(boundarySrc));
check('boundary has componentDidCatch', /componentDidCatch/.test(boundarySrc));
check('boundary renders fallbackText', /fallbackText/.test(boundarySrc));

const rendererSrc = read(files.renderer);
check('renderer has component registry', /COMPONENT_REGISTRY/.test(rendererSrc));
check('renderer registers probability_tree', /probability_tree/.test(rendererSrc));
check('renderer wraps in GenerativeUIErrorBoundary', /GenerativeUIErrorBoundary/.test(rendererSrc));
check('renderer falls back for unknown component', /FallbackNote/.test(rendererSrc));

const treeSrc = read(files.tree);
check('tree throws on missing props', /throw new Error/.test(treeSrc));

const chatSrc = read(files.chat);
check('ChatInterface imports GenerativeUIRenderer', /import\s*\{\s*GenerativeUIRenderer\s*\}/.test(chatSrc));
check('ChatInterface renders uiComponent branch', /msg\.uiComponent/.test(chatSrc));

// ─── 3. behavioral: reducer simulation for ui_component ─────────────────────────
// نُحاكي المنطق الموجود في useAgentSocket: حدث ui_component → رسالة مساعد مستقلة.
let idc = 0;
const generateId = () => `id-${++idc}`;

const reduceUiComponent = (prev, payload) => {
    const component = payload?.component;
    const props = payload?.props;
    const fallbackText = payload?.fallback_text || 'تعذّر عرض المكوّن.';
    if (typeof component === 'string' && component) {
        return [
            ...prev,
            {
                id: generateId(),
                role: 'assistant',
                content: '',
                isComplete: true,
                uiComponent: {
                    component,
                    props: props && typeof props === 'object' ? props : {},
                    fallbackText: String(fallbackText),
                },
            },
        ];
    }
    return prev;
};

// Live Test A (successful stream): UI event then text deltas
let messages = [{ id: 'u1', role: 'user', content: 'شجرة احتمالات' }];
messages = reduceUiComponent(messages, {
    component: 'probability_tree',
    props: { title: 'شجرة الاحتمالات', tree: { label: 'root', children: [] } },
    fallback_text: 'بديل',
});
const uiMsg = messages[messages.length - 1];
check('ui_component creates standalone assistant message', uiMsg.role === 'assistant' && !!uiMsg.uiComponent);
check('ui_component message is complete (does not block send button)', uiMsg.isComplete === true);
check('ui_component message carries component name', uiMsg.uiComponent.component === 'probability_tree');
check('ui_component message carries props', uiMsg.uiComponent.props.title === 'شجرة الاحتمالات');

// أول delta نصّي لاحق يجب أن يُنشئ رسالة منفصلة (لأن uiMsg.isComplete === true)
const last = messages[messages.length - 1];
const firstDeltaCreatesNewMessage = !(last.role === 'assistant' && !last.isComplete);
check('text delta after ui_component starts a NEW message (no merge)', firstDeltaCreatesNewMessage);

// Live Test B (fault tolerance): malformed payload → no message added
const before = messages.length;
messages = reduceUiComponent(messages, { component: null, props: 'garbage' });
check('malformed ui_component payload adds no message', messages.length === before);

// ─── 4. fault-tolerance: registry + boundary fallback logic ─────────────────────
const REGISTRY = { probability_tree: true, bkt_hint_display: true };
const renderDecision = (uiComponent) => {
    const c = uiComponent?.component;
    if (!REGISTRY[c]) return { kind: 'fallback', text: uiComponent?.fallbackText };
    return { kind: 'component', name: c };
};
check('unknown component → fallback', renderDecision({ component: 'evil', fallbackText: 'fb' }).kind === 'fallback');
check('known component → render', renderDecision({ component: 'probability_tree' }).kind === 'component');

// محاكاة getDerivedStateFromError: استثناء التصيير → عرض النص البديل
const simulateBoundary = (renderFn, fallbackText) => {
    try {
        renderFn();
        return { hasError: false };
    } catch (_e) {
        return { hasError: true, fallback: fallbackText };
    }
};
const malformedTreeRender = () => {
    const props = { tree: undefined };
    if (!props.tree || typeof props.tree !== 'object') throw new Error('missing tree');
};
const boundaryState = simulateBoundary(malformedTreeRender, 'النص البديل');
check('error boundary catches malformed tree render', boundaryState.hasError === true);
check('error boundary surfaces fallback text', boundaryState.fallback === 'النص البديل');

// ─── النتيجة ────────────────────────────────────────────────────────────────────
if (failed > 0) {
    console.log(`\n❌ ${failed} check(s) failed`);
    process.exit(1);
}
console.log('\n🎉 All generative-UI streaming checks passed');
