/**
 * ISS-121 (D-154) — Math Display Integrity Regression Tests.
 *
 * كارثتا العرض (screenshot الهاتف 2026-07-02):
 * 1. bidi scrambling: الصيغ ASCII (`C(5,3) = (5×4×3)/(3×2×1) = 10`) داخل فقرات RTL
 *    تتبعثر («= :(5 العدد)» و«10» يتيمة على سطر). الإصلاح: `_fmt_comb` يُخرج LaTeX
 *    (`$C_{5}^{3} = \dfrac{...}{...} = 10$`) — KaTeX يُصيّرها LTR-معزولة.
 * 2. النسخ المضاعف («1\n1») على Samsung/Android: التحديد الأصلي يتجاهل
 *    user-select:none على `.katex-mathml` فيلتقط annotation + المرئي.
 *    الإصلاح: `display: none !important` على `.katex-mathml`.
 *
 * تشغيل: node frontend/tests/iss121_math_display.test.mjs
 */

import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '..', '..');

let failed = 0;
const check = (name, cond, detail = '') => {
    if (cond) {
        console.log(`  ✅ ${name}`);
    } else {
        failed += 1;
        console.error(`  ❌ ${name}${detail ? ` — ${detail}` : ''}`);
    }
};

console.log('ISS-121 (D-154) — math display integrity:');

// ── 1. CSS: katex-mathml مخفي كلياً (يقتل النسخ المضاعف على الموبايل) ────────
const css = readFileSync(resolve(repoRoot, 'frontend', 'app', 'globals.css'), 'utf-8');
const mathmlBlock = css.split('.katex-mathml {')[1]?.split('}')[0] ?? '';
check('.katex-mathml has display:none !important', mathmlBlock.includes('display: none !important'));
check('.katex-mathml keeps user-select:none (defense in depth)', mathmlBlock.includes('user-select: none'));

// ── 2. Backend builders emit LaTeX, not raw ASCII fractions (bidi-safe) ──────
// D-163/D-168: عقل الاحتمالات مُفكَّك (brain root + probability_brain mixins +
// clients/orchestrator mixins) — نقرأ المصدر المُركَّب glob-اً ليصمد أي استخراج قادم.
const orch = [
    resolve(repoRoot, 'app', 'infrastructure', 'clients', 'orchestrator_client.py'),
    resolve(repoRoot, 'app', 'services', 'skills', 'probability_tutor_brain.py'),
    ...readdirSync(resolve(repoRoot, 'app', 'services', 'skills', 'probability_brain'))
        .filter((f) => f.endsWith('.py'))
        .sort()
        .map((f) => resolve(repoRoot, 'app', 'services', 'skills', 'probability_brain', f)),
    ...readdirSync(resolve(repoRoot, 'app', 'infrastructure', 'clients', 'orchestrator'))
        .filter((f) => f.endsWith('.py'))
        .sort()
        .map((f) => resolve(repoRoot, 'app', 'infrastructure', 'clients', 'orchestrator', f)),
]
    .map((f) => readFileSync(f, 'utf-8'))
    .join('\n');
check(
    '_fmt_comb emits LaTeX $C_{n}^{k}$ form',
    orch.includes('C_{{{c}}}^{{{k}}}') && orch.includes('\\\\dfrac'),
);
check(
    'old ASCII fraction template removed from _fmt_comb',
    !orch.includes('f"C({c},{k}) = ({num})/({den}) = {fav}"'),
);

// ── 3. Zero final-answer reveal (roadmap §7) in deterministic builders ────────
check(
    'reveal no longer prints «فاحتمال الحادثة A هو X من كل Y»',
    !orch.includes('فاحتمال الحادثة A هو {same} من كل {total}'),
);
check(
    'reveal ends with a generation question (ركّب الاحتمال بنفسك)',
    orch.includes('ركّب الاحتمال **بنفسك**'),
);

// ── 4. Orchestrator port mirrors the same contracts (M10-S2.1) ───────────────
const port = readFileSync(
    resolve(
        repoRoot,
        'microservices',
        'orchestrator_service',
        'src',
        'services',
        'overmind',
        'probability_tutor.py',
    ),
    'utf-8',
);
check('port emits LaTeX fmt_comb', port.includes('\\\\dfrac'));
// D-173 (M10-S2.4): يُبان **الكشف النهائي** (reveal dump «فاحتمال الحادثة A هو ...»)
// لا العبارة العلائقية للشارح المفاهيمي D-125 («{same} من كل {total}» = نسبة
// البسط/المقام، doctrine-parity مع العقل) — نظير حارس Python سطر 297/369.
check(
    'port never prints the P(A) reveal dump',
    !port.includes('فاحتمال الحادثة A هو {same} من كل {total}'),
);

if (failed > 0) {
    console.error(`\n${failed} ISS-121 check(s) failed`);
    process.exit(1);
}
console.log('\n🎉 all ISS-121 math-display checks pass');
