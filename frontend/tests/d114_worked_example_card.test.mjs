/**
 * D-114 — WorkedExampleCard — Regression Tests (source-inspection).
 *
 * يثبت أن بطاقة المثال المحلول المُتدرّج موصولة ومُسجَّلة:
 *  - المكوّن يقرأ steps + subgoal_label + subgoal_color + self_explanation_prompt.
 *  - كشف تدريجي تفاعلي (useState) + مقياس إتقان + جسر «جرّب تمرينك».
 *  - props مشوّهة (لا steps) → fallback آمن.
 *  - يستخدم MathText لتصيير LaTeX داخل التسميات/الأسئلة.
 *  - GenerativeUIRenderer يُسجّل worked_example_card.
 *  - CSS .genui-we-card موجود.
 *
 * تشغيل: node frontend/tests/d114_worked_example_card.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const read = (...p) => readFileSync(resolve(__dirname, '..', ...p), 'utf-8');

const card = read('app', 'components', 'generative', 'WorkedExampleCard.jsx');
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

console.log('D-114 — WorkedExampleCard regression\n');

check('reads steps array', card.includes('data.steps'));
check('reads subgoal_label', card.includes('subgoal_label'));
check('reads subgoal_color', card.includes('subgoal_color'));
check('reads self_explanation_prompt', card.includes('self_explanation_prompt'));
check('reads bridge_text', card.includes('bridge_text'));
check('mastery meter', card.includes('mastery') && card.includes('genui-we-mastery'));
check('progressive reveal (useState)', card.includes('useState') && card.includes('setRevealed'));
check('uses MathText for LaTeX', card.includes('import { MathText }') && card.includes('<MathText>'));
check('malformed-props fallback', card.includes('fallbackText'));
check('Arabic concept labels', card.includes('CONCEPT_LABELS'));

check('renderer imports WorkedExampleCard', renderer.includes('import { WorkedExampleCard }'));
check(
    'worked_example_card maps to WorkedExampleCard',
    /worked_example_card:[\s\S]*?WorkedExampleCard/.test(renderer)
);

check('CSS: .genui-we-card class', css.includes('.genui-we-card'));
check('CSS: mastery fill animated', css.includes('.genui-we-mastery-fill'));
check('CSS: step fade animation', css.includes('genui-we-fade'));
check('CSS: bridge style', css.includes('.genui-we-bridge'));

console.log(failed === 0 ? `\n🎉 All WorkedExampleCard checks passed` : `\n💥 ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
