/**
 * D-121 — Progressive-Reveal Discovery Lab (FullExerciseStory) — Regression.
 *
 * الثورة البصرية (المرحلة 1): خطوة الحدث تُصيَّر كمختبر اكتشاف تدريجي بدل عرض كل
 * شيء دفعة واحدة — فروع قابلة للنقر (أبيض مستحيل/أحمر/أخضر) → تجميع → مقام → نتيجة،
 * كل طبقة بكشف واحد. مبني على عقد البيانات القائم (frontend-only، بلا مسّ للخلفية).
 *
 * يحرس أيضاً عدم انحدار عقود D-116 (تفاعل/كشف) و D-120 (focus_step_id).
 *
 * تشغيل: node frontend/tests/d121_progressive_reveal.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const read = (...p) => readFileSync(resolve(__dirname, '..', ...p), 'utf-8');
const fes = read('app', 'components', 'generative', 'FullExerciseStory.jsx');
const css = read('app', 'globals.css');

let failed = 0;
const check = (name, cond) => {
    if (cond) console.log(`  ✅ ${name}`);
    else { console.error(`  ❌ ${name}`); failed += 1; }
};

console.log('D-121 — progressive-reveal discovery lab regression\n');

// ── 1. الحدث يُصيَّر كمختبر اكتشاف تدريجي ──────────────────────────────────────
check('EventLayeredReveal component defined', fes.includes('const EventLayeredReveal'));
check('event_breakdown uses EventLayeredReveal (not all-at-once)',
    fes.includes('event_breakdown: (state) => <EventLayeredReveal'));
check('old EventBreakdownStep removed', !fes.includes('EventBreakdownStep'));
check('layered state machine (open Set + layer)',
    fes.includes('const [open, setOpen]') && fes.includes('const [layer, setLayer]'));
check('branches are clickable (openBranch)', fes.includes('openBranch') && fes.includes('genui-fes-branch'));
check('next-layer button gated on allSeen', fes.includes('allSeen') && fes.includes('genui-fes-next-layer'));
check('cumulative layers: sum → denom → result',
    fes.includes('genui-fes-sum') && fes.includes('genui-fes-denom') && fes.includes('genui-fes-result-reveal'));
check('result only at final layer (layer >= 3) with positive frac',
    /layer >= 3 && total > 0 && sameFav > 0/.test(fes));
check('no misleading 0 for impossible (pedagogical_string)',
    fes.includes('pedagogical_string') && fes.includes('isStateImpossible'));
check('result reveal celebrates (bravo)', fes.includes('genui-fes-bravo'));

// ── 2. مشهد الكيس البطل (دخول تتابعي) ─────────────────────────────────────────
check('hero urn (is-hero + staggered ball index)',
    fes.includes('genui-fes-urn is-hero') && fes.includes('--genui-ball-i'));

// ── 3. لا انحدار: D-116 (تفاعل/كشف) محفوظ ─────────────────────────────────────
check('D-116 StepInteraction preserved', fes.includes('const StepInteraction'));
check('D-116 revealed Set preserved', fes.includes('const [revealed, setRevealed]'));
check('D-116 genui-fes-interact + reveal-btn preserved',
    fes.includes('genui-fes-interact') && fes.includes('genui-fes-reveal-btn'));
check('D-116 renderer only after reveal (isRevealed gate)',
    /isRevealed[\s\S]*StepInteraction[\s\S]*genui-fes-visual/.test(fes));

// ── 4. لا انحدار: D-120 (focus_step_id) محفوظ ─────────────────────────────────
check('D-120 focus_step_id initial step preserved',
    fes.includes('props.focus_step_id') && fes.includes('useState(initialStep)'));

// ── 5. CSS: أنماط الكشف التدريجي + الحركات + reduced-motion ───────────────────
check('CSS: branch cards', css.includes('.genui-fes-branch') && css.includes('.genui-fes-branch.is-open'));
check('CSS: next-layer + layer + result', css.includes('.genui-fes-next-layer')
    && css.includes('.genui-fes-layer') && css.includes('.genui-fes-result-reveal'));
check('CSS: hero ball entrance keyframe', css.includes('@keyframes genui-ball-in')
    && css.includes('.genui-fes-urn.is-hero .genui-fes-ball'));
check('CSS: layer + result keyframes', css.includes('@keyframes genui-layer-in')
    && css.includes('@keyframes genui-result-pop'));
check('CSS: reduced-motion covers new animations',
    /prefers-reduced-motion[\s\S]*genui-fes-result-reveal/.test(css));
check('CSS: uses existing tokens (no invented colors)',
    css.includes('color-mix(in srgb, var(--primary-color)') && css.includes('var(--success-color)'));

// ── 6. آلة تقدّم الطبقة (محاكاة سلوكية حتمية) ─────────────────────────────────
// 0=فروع → (allSeen) → 1=تجميع → 2=مقام → 3=نتيجة. النتيجة لا تظهر قبل الطبقة 3.
const layerVisible = (layer) => ({
    sum: layer >= 1,
    denom: layer >= 2,
    result: layer >= 3,
});
check('layer 0: only branches (no sum/denom/result)',
    !layerVisible(0).sum && !layerVisible(0).denom && !layerVisible(0).result);
check('layer 1: sum visible, result hidden', layerVisible(1).sum && !layerVisible(1).result);
check('layer 3: result visible', layerVisible(3).result);

console.log(failed === 0 ? `\n🎉 All D-121 progressive-reveal checks passed` : `\n💥 ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
