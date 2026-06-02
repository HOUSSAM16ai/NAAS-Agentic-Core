// ISS-106 (D-WS-CARD-PERSIST-001) — regression: persisted generative-UI cards
// survive logout/login by being mapped from the backend `ui_component` (snake,
// wire shape {component, props, fallback_text}) onto each history message's
// `uiComponent` (camel) inside setMessagesSafe — the exact shape GenerativeUIRenderer
// expects. This faithfully replays the setMessagesSafe normalization logic.
//
// Run: node frontend/tests/iss106_card_persistence.test.mjs

let pass = 0, fail = 0;
const ok = (name, cond) => { if (cond) { pass++; console.log('✅', name); } else { fail++; console.log('❌', name); } };

let _id = 0;
const generateId = () => `gen-${++_id}`;

// ── verbatim port of setMessagesSafe normalization (useAgentSocket.js) ──
function setMessagesSafe(msgs) {
    if (!Array.isArray(msgs)) return [];
    return msgs.map((msg) => {
        if (!msg || typeof msg !== 'object') return msg;
        const next = { ...msg };
        if (next.id === undefined || next.id === null) next.id = generateId();
        if (next.role === 'assistant' && next.isComplete !== true) next.isComplete = true;
        // ISS-106: map persisted ui_component (snake/wire) -> uiComponent (camel).
        if (!next.uiComponent && next.ui_component && typeof next.ui_component === 'object') {
            const uc = next.ui_component;
            if (typeof uc.component === 'string' && uc.component) {
                next.uiComponent = {
                    component: uc.component,
                    props: uc.props && typeof uc.props === 'object' ? uc.props : {},
                    fallbackText: String(uc.fallback_text || uc.fallbackText || 'تعذّر عرض المكوّن.'),
                };
            }
        }
        return next;
    });
}

// render guard from ChatInterface.jsx:281
const wouldRenderCard = (m) => m.role === 'assistant' && m.isComplete === true && !!m.uiComponent;

// ── Scenario: history payload exactly as the backend now returns it ──
// (GET /api/chat/conversations/{id} → messages with ui_component)
const history = [
    { role: 'user', content: 'اعطني تمرين دوال 2016', created_at: '2026-06-02T00:00:00Z', policy_flags: null, ui_component: null },
    // standalone BKT card row (content="") — persisted by _persist_ui_component_cards
    {
        role: 'assistant', content: '', created_at: '2026-06-02T00:00:01Z', policy_flags: null,
        ui_component: { component: 'bkt_hint_display', props: { concept_id: 'numerical_functions', student_mastery_probability: 0.16 }, fallback_text: 'تتبّع المعرفة: numerical_functions — إتقان 16%' },
    },
    // assistant text row with attached math card
    {
        role: 'assistant', content: '## التمرين الرابع ...', created_at: '2026-06-02T00:00:02Z', policy_flags: null,
        ui_component: { component: 'math_explanation_card', props: { math_type: 'derivative', steps: [] }, fallback_text: 'بطاقة شرح رياضي' },
    },
];

const out = setMessagesSafe(history);

ok('all history messages mapped (3)', out.length === 3);
ok('user message untouched (no uiComponent)', !out[0].uiComponent);
ok('assistant messages flagged isComplete:true', out[1].isComplete === true && out[2].isComplete === true);

// BKT card-only row
const bkt = out[1];
ok('BKT row: uiComponent created', !!bkt.uiComponent);
ok('BKT row: component preserved', bkt.uiComponent?.component === 'bkt_hint_display');
ok('BKT row: props preserved', bkt.uiComponent?.props?.concept_id === 'numerical_functions');
ok('BKT row: fallback_text -> fallbackText', bkt.uiComponent?.fallbackText.includes('تتبّع المعرفة'));
ok('BKT row would render its card (content="" allowed)', wouldRenderCard(bkt));

// math card attached to text row
const math = out[2];
ok('math row: uiComponent created', !!math.uiComponent);
ok('math row: component preserved', math.uiComponent?.component === 'math_explanation_card');
ok('math row: text content preserved alongside card', math.content.startsWith('## التمرين'));
ok('math row would render its card', wouldRenderCard(math));

// idempotency: a message that already has uiComponent (live) is not overwritten
const live = setMessagesSafe([{ role: 'assistant', content: 'x', isComplete: true, uiComponent: { component: 'probability_tree', props: {}, fallbackText: 'fb' } }]);
ok('live uiComponent not clobbered', live[0].uiComponent?.component === 'probability_tree');

// malformed ui_component is ignored (no crash, no bogus card)
const bad = setMessagesSafe([{ role: 'assistant', content: 'y', ui_component: { props: {} } }]);
ok('malformed ui_component (no component) ignored', !bad[0].uiComponent);

// null ui_component ignored
const nul = setMessagesSafe([{ role: 'assistant', content: 'z', ui_component: null }]);
ok('null ui_component ignored', !nul[0].uiComponent);

console.log(`\n${fail === 0 ? '🎉' : '💥'} ISS-106 D-WS-CARD-PERSIST-001 — ${pass} passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
