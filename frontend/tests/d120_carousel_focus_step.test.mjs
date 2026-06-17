/**
 * D-120 — Carousel opens at the asked step (focus_step_id) — Regression.
 *
 * الكارثة: الكاروسيل كان يفتح دائماً على الخطوة 1 (الكيس/فهم المعطيات) ويتجاهل
 * `props.focus_step_id` المُمرَّر. فسؤال P(A) (focus_step_id="same_color_event")
 * يُعيد «فهم المعطيات» كل مرة ⇒ إحساس التكرار/عدم التقدّم.
 *
 * D-120: يُهيَّأ `active` إلى فهرس الخطوة التي step_id === focus_step_id (fallback 0).
 *
 * تشغيل: node frontend/tests/d120_carousel_focus_step.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const read = (...p) => readFileSync(resolve(__dirname, '..', ...p), 'utf-8');
const fes = read('app', 'components', 'generative', 'FullExerciseStory.jsx');

let failed = 0;
const check = (name, cond) => {
    if (cond) console.log(`  ✅ ${name}`);
    else { console.error(`  ❌ ${name}`); failed += 1; }
};

console.log('D-120 — carousel focus-step regression\n');

// ── 1. Source: focus_step_id drives the initial active step ──────────────────
check('reads props.focus_step_id', fes.includes('props.focus_step_id'));
check('computes initialStep via findIndex on step_id', fes.includes('findIndex') && fes.includes('s.step_id === focusId'));
check('useState seeded with initialStep (not 0)', fes.includes('useState(initialStep)'));
check('fallback to 0 when no match', fes.includes('idx >= 0 ? idx : 0'));
check('no longer hard-coded useState(0)', !fes.includes('const [active, setActive] = useState(0)'));

// ── 2. Behavioral replica of the initial-step logic ──────────────────────────
// نُحاكي المنطق الحتمي: same_color_event ⇒ خطوة الحدث (الفهرس 2).
const STEPS = [
    { step_id: 'data' },
    { step_id: 'sample_space' },
    { step_id: 'same_color_event' },
    { step_id: 'random_variable' },
];
const initialStepIndex = (steps, focusId) => {
    if (!focusId) return 0;
    const idx = steps.findIndex((s) => s && s.step_id === focusId);
    return idx >= 0 ? idx : 0;
};
check('P(A) → same_color_event opens event step (idx 2)',
    initialStepIndex(STEPS, 'same_color_event') === 2);
check('E(X) → random_variable opens distribution step (idx 3)',
    initialStepIndex(STEPS, 'random_variable') === 3);
check('sample_space → idx 1', initialStepIndex(STEPS, 'sample_space') === 1);
check('no focus → urn step (idx 0)', initialStepIndex(STEPS, '') === 0);
check('unknown focus → fallback idx 0', initialStepIndex(STEPS, 'nope') === 0);

console.log(failed === 0 ? `\n🎉 All D-120 carousel focus-step checks passed` : `\n💥 ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
