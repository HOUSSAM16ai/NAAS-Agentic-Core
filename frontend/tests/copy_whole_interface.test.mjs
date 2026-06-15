// كارثة «نسخ كامل الواجهة يُظهر سلسلة طويلة من الأكواد البرمجية» (D-WS-COPY-002):
// تحديد الكل (Ctrl+A) عبر محادثة فيها رياضيات كان يجمع مصدر TeX الخام من كل صيغة.
// الإصلاح: (1) .katex-mathml { user-select:none } عالمياً + (2) معالج copy عام
// يُنظّف التحديد عبر markdownToPlainText. هذا الاختبار يغطّي الطبقة المنطقية (2)
// + فحص بنيوي للطبقتين في الملفات.
//
// تشغيل: node frontend/tests/copy_whole_interface.test.mjs
import { markdownToPlainText } from '../app/utils/preprocessMath.js';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dir = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dir, '..');

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

// 1) محاكاة «نسخ كامل الواجهة»: تحديد متعدد الرسائل فيه مصدر LaTeX خام
//    (كما لو سرّبته KaTeX أو بقي في النص). يجب أن يخرج نظيفاً بلا أكواد.
const WHOLE_INTERFACE = [
    'الطالب: اشرح لي التمرين',
    'المعلم: لتكن $g(x) = 1 + (x^2+x-1)e^{-x}$ على $\\mathbb{R}$.',
    'نحسب $$\\lim_{x \\to -\\infty} g(x)$$ ثم $\\frac{a}{b} \\leq \\sqrt{2}$.',
    'عدد الطرق $\\binom{11}{3}$ و $$P(A) = \\frac{\\binom{4}{3}+\\binom{5}{3}}{\\binom{11}{3}}$$',
    '## ملخص',
    '| اللون | العدد |',
    '|---|---|',
    '| أحمر | 4 |',
].join('\n');

const cleaned = markdownToPlainText(WHOLE_INTERFACE);
console.log('--- cleaned whole-interface copy ---\n' + cleaned + '\n------------------------------------');

check('no LaTeX backslash commands', !cleaned.includes('\\'), cleaned);
check('no $ math delimiters', !cleaned.includes('$'));
check('no \\binom/\\frac/\\mathbb literals', !/\\(binom|frac|mathbb|lim|sqrt)/.test(cleaned));
check('no markdown table pipes', !cleaned.includes('|'));
check('no heading hashes', !/^#{1,6}\s/m.test(cleaned));
check('Arabic prose preserved', cleaned.includes('اشرح لي التمرين') && cleaned.includes('ملخص'));
check('math content readable (ℝ / ≤ / →)', cleaned.includes('ℝ') && cleaned.includes('≤'));
check('empty selection → empty', markdownToPlainText('') === '');

// 2) فحص بنيوي: القاعدة العامة لـ katex-mathml (غير مقصورة على حاوية)
const css = readFileSync(join(ROOT, 'app/globals.css'), 'utf-8');
check(
    'globals.css has GLOBAL .katex-mathml user-select:none',
    /(^|\n)\.katex-mathml\s*\{[^}]*user-select:\s*none/.test(css),
    'global rule missing',
);
check(
    'katex-mathml rule is not container-scoped only',
    !/\.markdown-content\s+\.katex-mathml\s*,/.test(css),
    'still scoped to .markdown-content',
);

// 3) فحص بنيوي: معالج copy عام في CogniForgeApp
const app = readFileSync(join(ROOT, 'app/components/CogniForgeApp.jsx'), 'utf-8');
check('CogniForgeApp imports markdownToPlainText', app.includes("markdownToPlainText"));
check(
    "CogniForgeApp registers document 'copy' listener",
    /addEventListener\(\s*['"]copy['"]/.test(app),
);
check(
    'copy handler sanitizes via markdownToPlainText + preventDefault',
    app.includes('markdownToPlainText(selected)') && /preventDefault\(\)/.test(app),
);
check(
    'copy handler skips input/textarea',
    /input.*textarea|textarea.*input/.test(app) && app.includes('isContentEditable'),
);

console.log(`\nRESULT: ${pass}/${pass + fail} checks passed`);
process.exit(fail === 0 ? 0 : 1);
