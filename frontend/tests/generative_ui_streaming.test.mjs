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

// ─── 5. Cognitive UI overhaul: SVG tree + glass nodes (V3) ──────────────────────
check('tree uses SVG (not flexbox list)', /<svg/.test(treeSrc) && /viewBox/.test(treeSrc));
check('tree draws bezier edge paths', /<path/.test(treeSrc) && /C \$\{/.test(treeSrc));
check('edge stroke-width scales with probability', /strokeWidthFor/.test(treeSrc));
check('nodes are glass-morphism cards (foreignObject)', /foreignObject/.test(treeSrc) && /genui-glass-node/.test(treeSrc));
// V4: tooltip is rendered via React Portal to document.body (escapes SVG clipping)
check('interactive tooltip with conditional formula', /genui-tip-portal/.test(treeSrc) && /P\(\$\{node\.label\}\)/.test(treeSrc));
check('V4: tooltip uses createPortal to document.body (no SVG z-index clipping)', /createPortal/.test(treeSrc) && /document\.body/.test(treeSrc));
check('V4: old inline in-SVG tooltip removed', !/genui-node-tip/.test(treeSrc));
check('V4: probabilities humanized to fractions (decimalToFraction)', /decimalToFraction/.test(treeSrc));
check('V4: semantic outcome classification (success/failure)', /classifyOutcome/.test(treeSrc) && /'failure'/.test(treeSrc));
check('V4: per-outcome edge gradients', /genui-edge-\$\{outcome\}/.test(treeSrc));
check('V4: css portal tooltip floats above (high z-index)', /genui-tip-portal/.test(read('globals.css')) && /z-index:\s*99999/.test(read('globals.css')));
check('V4: css semantic outcome node colours', /data-outcome='success'/.test(read('globals.css')) && /data-outcome='failure'/.test(read('globals.css')));
check('V4: css fraction styling', /genui-frac/.test(read('globals.css')));
check('cumulative path joint probability computed', /joint/.test(treeSrc));
check('recursive layout (tidy-tree) implemented', /layoutTree/.test(treeSrc) && /maxDepth/.test(treeSrc));
check('large-tree guard throws (ErrorBoundary fallback)', /tree too large/.test(treeSrc));
check('css: energy-flow edge animation', /genui-edge-flow/.test(read('globals.css')));
check('css: staggered node spawn animation', /genui-node-spawn/.test(read('globals.css')));
check('css: glass-morphism backdrop-blur', /backdrop-filter:\s*blur/.test(read('globals.css')));
check('css: reduced-motion accessibility', /prefers-reduced-motion/.test(read('globals.css')));

// behavioral: layout assigns leaf rows + internal node = mean(children), joint = product
const simulateLayout = (root) => {
    const nodes = [];
    let leaf = 0;
    let maxDepth = 0;
    const walk = (node, depth, joint) => {
        maxDepth = Math.max(maxDepth, depth);
        const p = typeof node.p === 'number' ? node.p : null;
        const nodeJoint = p !== null ? joint * p : joint;
        const rec = { depth, label: node.label, p, joint: nodeJoint, row: 0 };
        nodes.push(rec);
        const children = Array.isArray(node.children) ? node.children : [];
        if (children.length === 0) {
            rec.row = leaf++;
        } else {
            const rows = children.map((c) => walk(c, depth + 1, nodeJoint).row);
            rec.row = rows.reduce((s, r) => s + r, 0) / rows.length;
        }
        return rec;
    };
    walk(root, 0, 1);
    return { nodes, leafCount: Math.max(1, leaf), maxDepth };
};

const sampleTree = {
    label: 'البداية',
    children: [
        { label: 'A', p: 0.3, children: [{ label: 'B | A', p: 0.8 }, { label: 'B̄ | A', p: 0.2 }] },
        { label: 'Ā', p: 0.7, children: [{ label: 'B | Ā', p: 0.5 }, { label: 'B̄ | Ā', p: 0.5 }] },
    ],
};
const layout = simulateLayout(sampleTree);
check('layout: 7 nodes for 2-level binary tree', layout.nodes.length === 7);
check('layout: 4 leaves', layout.leafCount === 4);
check('layout: maxDepth = 2', layout.maxDepth === 2);
const leafBA = layout.nodes.find((n) => n.label === 'B | A');
check('joint probability P(A)·P(B|A) = 0.24', Math.abs(leafBA.joint - 0.24) < 1e-9);
const rootNode = layout.nodes.find((n) => n.label === 'البداية');
check('root row = mean of subtree (centered)', rootNode.row === 1.5);

// ─── V30.0: CombinationsVisualizer — Sub-Group Leak + Deep Dive ──────────────────
const combSrc = read('components/generative/CombinationsVisualizer.jsx');
check('V30: reads is_possible flag', /is_possible/.test(combSrc));
check('V30: renders pedagogical_string for impossible group', /pedagogical_string/.test(combSrc));
check(
    'V30: impossible branch does NOT render SymbolCnk (no C_n^k = 0 leak)',
    /isPossible\s*\?[\s\S]*?SymbolCnk[\s\S]*?:\s*\([\s\S]*?genui-comb-impossible/.test(combSrc),
);
check('V30: deep_dive prop consumed', /deep_dive/.test(combSrc));
check('V30: urn_state visualized (UrnState)', /UrnState/.test(combSrc) && /urn_state/.test(combSrc));
check('V30: color tokens mapped (urn balls)', /COLOR_TOKENS/.test(combSrc));

// behavioral: simulate the guardrail rendering decision per group
const renderGroup = (g, k) => {
    const isPossible = g.is_possible !== false;
    if (isPossible) return { kind: 'formula', text: `C(${g.count},${k}) = ${g.favorable_combinations}` };
    return { kind: 'pedagogical', text: g.pedagogical_string || 'مستحيل لهذا الصنف فقط (العدد المتوفر غير كافٍ لسحب المطلوب)' };
};
const whiteGroup = { label: 'كرة بيضاء', count: 2, favorable_combinations: 0, is_possible: false, pedagogical_string: 'مستحيل لهذا الصنف فقط (العدد المتوفر غير كافٍ لسحب المطلوب)' };
const redGroup = { label: 'كرة حمراء', count: 4, favorable_combinations: 4, is_possible: true };
const wr = renderGroup(whiteGroup, 3);
const rr = renderGroup(redGroup, 3);
check('V30: white(2) drawing 3 → pedagogical, not formula', wr.kind === 'pedagogical' && !/C\(/.test(wr.text));
check('V30: red(4) drawing 3 → formula C(4,3) = 4', rr.kind === 'formula' && rr.text === 'C(4,3) = 4');

// ─── النتيجة ────────────────────────────────────────────────────────────────────
if (failed > 0) {
    console.log(`\n❌ ${failed} check(s) failed`);
    process.exit(1);
}
console.log('\n🎉 All generative-UI streaming checks passed');
