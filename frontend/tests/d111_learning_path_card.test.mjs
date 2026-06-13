/**
 * D-111 — LearningPathCard — Regression Tests (source-inspection).
 *
 * يثبت أن بطاقة المسار التعلّمي موصولة ومُسجَّلة:
 *  - المكوّن يقرأ recommendation_text + target_difficulty + advanced + next_concept.
 *  - props مشوّهة (لا recommendation_text) → fallback آمن.
 *  - GenerativeUIRenderer يُسجّل learning_path_card.
 *  - CSS .genui-path-card موجود.
 *
 * تشغيل: node frontend/tests/d111_learning_path_card.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const read = (...p) => readFileSync(resolve(__dirname, '..', ...p), 'utf-8');

const card = read('app', 'components', 'generative', 'LearningPathCard.jsx');
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

console.log('D-111 — LearningPathCard regression\n');

check('reads recommendation_text', card.includes('recommendation_text'));
check('reads target_difficulty', card.includes('target_difficulty'));
check('reads advanced flag', card.includes('advanced'));
check('reads next_concept', card.includes('next_concept'));
check('Arabic concept labels', card.includes('الأعداد المركبة') && card.includes('CONCEPT_LABELS'));
check('difficulty map (easy/medium/hard)', /easy[\s\S]*medium[\s\S]*hard/.test(card));
check('malformed-props fallback', card.includes('fallbackText'));

check('renderer imports LearningPathCard', renderer.includes('import { LearningPathCard }'));
check('learning_path_card maps to LearningPathCard', /learning_path_card:[\s\S]*?LearningPathCard/.test(renderer));

check('CSS: .genui-path-card class', css.includes('.genui-path-card'));
check('CSS: difficulty colors reuse mastery vars', css.includes('.genui-path-diff-hard'));

console.log(failed === 0 ? `\n🎉 All LearningPathCard checks passed` : `\n💥 ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
