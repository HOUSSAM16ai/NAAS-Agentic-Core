/**
 * ISS-114 (D-106) — BktMasteryCard — Regression Tests (source-inspection).
 *
 * يثبت أن بطاقة الإتقان المعرفي الحقيقية استبدلت الـ stub:
 *  - المكوّن موجود ويقرأ student_mastery_probability + concept_id + cognitive_load.
 *  - تدرّج لوني بعتبات الإتقان (0.7 / 0.35) عبر 3 CSS vars.
 *  - props مشوّهة (mastery غير رقمي) → fallback آمن لا انهيار.
 *  - GenerativeUIRenderer يُسجّل BktMasteryCard لا BktHintStub.
 *  - CSS vars + reduced-motion override موجودة.
 *
 * تشغيل: node frontend/tests/iss114_bkt_mastery_card.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const read = (...p) => readFileSync(resolve(__dirname, '..', ...p), 'utf-8');

const card = read('app', 'components', 'generative', 'BktMasteryCard.jsx');
const renderer = read('app', 'components', 'generative', 'GenerativeUIRenderer.jsx');
const css = read('app', 'globals.css');

let failed = 0;
const check = (name, cond) => {
    if (cond) {
        console.log(`  ✅ ${name}`);
    } else {
        console.error(`  ❌ ${name}`);
        failed += 1;
    }
};

console.log('ISS-114 D-106 — BktMasteryCard regression\n');

// المكوّن
check('reads student_mastery_probability', card.includes('student_mastery_probability'));
check('reads concept_id', card.includes('concept_id'));
check('reads cognitive_load_estimate', card.includes('cognitive_load_estimate'));
check('SVG progress ring (strokeDashoffset)', card.includes('strokeDashoffset'));
check('mastery band threshold 0.7', card.includes('0.7'));
check('mastery band threshold 0.35', card.includes('0.35'));
check('clamps mastery to [0,1]', card.includes('Math.max(0, Math.min(1'));
check('Arabic concept label map', card.includes('CONCEPT_LABELS') && card.includes('الأعداد المركبة'));
check('malformed-props fallback (Number.isFinite guard)', card.includes('Number.isFinite'));
check('fallbackText path preserved', card.includes('fallbackText'));

// التسجيل في الـ renderer
check('renderer imports BktMasteryCard', renderer.includes("import { BktMasteryCard }"));
check('bkt_hint_display maps to BktMasteryCard', /bkt_hint_display:[\s\S]*?BktMasteryCard/.test(renderer));
check('old BktHintStub removed', !renderer.includes('const BktHintStub'));

// CSS
check('CSS: --genui-mastery-high var defined', css.includes('--genui-mastery-high'));
check('CSS: --genui-mastery-low var defined', css.includes('--genui-mastery-low'));
check('CSS: .genui-bkt-card class', css.includes('.genui-bkt-card'));
check('CSS: genui-ring-fill keyframe', css.includes('@keyframes genui-ring-fill'));
// D-199: القائمة الصريحة استُبدلت بإعلانٍ شامل (`*`) يغطّي كلّ حركة، ومنها هذه.
// الصيغة القديمة كانت تطلب اسم المحدِّد نصّاً، وهي تفشل مع تغطيةٍ **أوسع** لا أضيق —
// فنختبر الضمان نفسه: هل تُوقَف هذه الحركة عند طلب تقليل الحركة؟
check('CSS: reduced-motion covers ring fill',
    /@media \(prefers-reduced-motion: reduce\)\s*\{[\s\S]*?\*,[\s\S]*?animation-duration/.test(css));

console.log(failed === 0 ? `\n🎉 All BktMasteryCard checks passed` : `\n💥 ${failed} check(s) failed`);
process.exit(failed === 0 ? 0 : 1);
