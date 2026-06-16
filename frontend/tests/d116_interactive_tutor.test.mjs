/**
 * D-116 — Interactive Probability Tutor (FullExerciseStory upgrade) — Regression.
 *
 * يثبت أن الكاروسيل البصري صار تفاعلياً (سؤال → تحقق → كشف):
 *  - StepInteraction: سؤال + choice/number + تحقق + تلميح + «اكشف الخطوة».
 *  - حالة revealed: المحتوى (renderer) يُكشف بعد المحاولة/الكشف، لا قبله.
 *  - شريط تقدّم. مشهد الكيس (UrnStep) محفوظ. لا LLM.
 *  - الخلفية الحتمية تضخّ step.interactive (probability_skill).
 *
 * تشغيل: node frontend/tests/d116_interactive_tutor.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const read = (...p) => readFileSync(resolve(__dirname, '..', ...p), 'utf-8');

const fes = read('app', 'components', 'generative', 'FullExerciseStory.jsx');
const css = read('app', 'globals.css');
const skill = readFileSync(
    resolve(__dirname, '..', '..', 'app', 'services', 'skills', 'probability_skill.py'),
    'utf-8',
);

let failed = 0;
const check = (name, cond) => {
    if (cond) console.log(`  ✅ ${name}`);
    else { console.error(`  ❌ ${name}`); failed += 1; }
};

console.log('D-116 — Interactive Probability Tutor regression\n');

// StepInteraction component
check('StepInteraction defined', fes.includes('const StepInteraction'));
check('reads step.interactive question', fes.includes('q.question') && fes.includes('interactive'));
check('choice answer kind', fes.includes("q.answer_kind === 'choice'") && fes.includes('expected_index'));
check('number answer kind + verify', fes.includes("q.answer_kind === 'number'") && fes.includes('q.expected'));
check('hint shown on wrong attempt', fes.includes('setShowHint') && fes.includes('q.hint'));
check('reveal-anyway button (no trap)', fes.includes('genui-fes-reveal-btn') && fes.includes('اكشف الخطوة'));

// Reveal gating: content hidden until revealed
check('revealed Set state', fes.includes('const [revealed, setRevealed]') && fes.includes('new Set'));
check('content gated behind isRevealed', fes.includes('isRevealed') && fes.includes('!isRevealed'));
check('renderer only after reveal', /isRevealed[\s\S]*StepInteraction[\s\S]*genui-fes-visual/.test(fes));
check('urn scene preserved (UrnStep)', fes.includes('UrnStep'));
check('progress bar', fes.includes('genui-fes-progress') && fes.includes('progressPct'));

// CSS
check('CSS: interaction styles', css.includes('.genui-fes-interact') && css.includes('.genui-fes-question'));
check('CSS: verify button', css.includes('.genui-fes-verify'));
check('CSS: progress fill', css.includes('.genui-fes-progress-fill'));

// Backend deterministic interactive data
check('ExerciseStep.interactive field', skill.includes('interactive: dict[str, object]'));
check('data step asks "هل يهمّ الترتيب"', skill.includes('هل يهمّ ترتيب'));
check('sample_space expects C(n,k)', skill.includes('"expected": total_comb'));
check('event step expects same_group', skill.includes('"expected": same_group'));
check('hints present (no LLM)', skill.includes('"hint":'));

console.log(failed === 0 ? `\n🎉 All D-116 interactive tutor checks passed` : `\n💥 ${failed} failed`);
process.exit(failed === 0 ? 0 : 1);
