// كارثة «نسخ الواجهة يُظهر أكواد برمجية»: زرّ النسخ كان ينسخ msg.content الخام
// (markdown + LaTeX). markdownToPlainText يحوّله إلى نص عربي نظيف قابل للقراءة.
//
// تشغيل: node frontend/tests/copy_plaintext.test.mjs
import { markdownToPlainText } from '../app/utils/preprocessMath.js';

let pass = 0;
let fail = 0;
function check(name, cond, extra = '') {
    if (cond) {
        pass++;
        console.log('  ✅ ' + name);
    } else {
        fail++;
        console.log('  ❌ ' + name + (extra ? '  → ' + extra : ''));
    }
}

// محتوى BAC تمثيلي حقيقي (markdown + LaTeX مختلط).
const SAMPLE = [
    '## دراسة الدالة',
    'لتكن $g(x) = 1 + (x^2+x-1)e^{-x}$ المعرّفة على $\\mathbb{R}$.',
    'نحسب $$\\lim_{x \\to -\\infty} g(x) = +\\infty$$',
    'ومنه $\\frac{a}{b} \\leq \\sqrt{2}$ و **النتيجة** في $\\boxed{14/165}$.',
    '',
    '| العمود الأول | العمود الثاني |',
    '|---|---|',
    '| قيمة 1 | قيمة 2 |',
    '',
    '- عنصر أول',
    '- عنصر ثانٍ',
].join('\n');

const out = markdownToPlainText(SAMPLE);
console.log('--- plain output ---\n' + out + '\n--------------------');

// 1) لا رموز «كود» تصل الطالب
check('no $ delimiters', !out.includes('$'), out);
check('no backslash commands', !out.includes('\\'), out);
check('no \\boxed/\\frac/\\sqrt literals', !/\\(boxed|frac|sqrt|mathbb|lim)/.test(out));
check('no markdown headings (##)', !/^#{1,6}\s/m.test(out));
check('no bold markers (**)', !out.includes('**'));
check('no table pipes (|---|)', !out.includes('|'));

// 2) المحتوى الرياضي تحوّل لنص مقروء (Unicode)
check('mathbb R → ℝ', out.includes('ℝ'));
check('\\leq → ≤', out.includes('≤'));
check('\\to → →', out.includes('→'));
check('\\infty → ∞', out.includes('∞'));
check('\\sqrt{2} → √(2)', out.includes('√(2)'));
check('\\frac{a}{b} → (a)/(b)', out.includes('(a)/(b)'));
check('\\boxed{14/165} → 14/165 (content kept, box removed)', out.includes('14/165'));
check('superscript x^2 readable', out.includes('x^2') || out.includes('x^(2)'));

// 3) النص العربي العادي محفوظ
check('Arabic prose preserved', out.includes('دراسة الدالة') && out.includes('النتيجة'));
check('list items kept as bullets', out.includes('عنصر أول') && out.includes('عنصر ثانٍ'));

// 4) حالات حدّية
check('empty → empty string', markdownToPlainText('') === '');
check('null-safe', markdownToPlainText(null) === '' && markdownToPlainText(undefined) === '');
check(
    'plain Arabic unchanged (no markup)',
    markdownToPlainText('السلام عليكم كيف حالك') === 'السلام عليكم كيف حالك',
);
check(
    'double-backslash LaTeX (knowledge_base style) cleaned',
    (() => {
        const r = markdownToPlainText('الدالة \\\\(g\\\\) معرّفة على \\\\(\\\\mathbb{R}\\\\)');
        return !r.includes('\\') && r.includes('g') && r.includes('ℝ');
    })(),
);

console.log(`\nRESULT: ${pass}/${pass + fail} checks passed`);
process.exit(fail === 0 ? 0 : 1);
