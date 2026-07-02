/**
 * ISS-120 (D-153) — `inert` Boolean Attribute Regression Tests.
 *
 * كارثة 2026-07-02 (screenshot المستخدم): Next.js error overlay يظهر للطالب على
 * الهاتف: «Received the string `true` for the boolean attribute `inert`» في
 * CogniForgeApp.jsx (DashboardLayout — الشريطان الجانبيان).
 *
 * السبب الجذري: commit «rendering integrity» مرَّر `inert` كسلسلة نصية:
 *   inert={!isAgentSidebarOpen ? "true" : undefined}
 * React 19 يعامل `inert` كسمة boolean — تمرير "true"/"false" النصية يُطلق
 * تحذير console يرفعه Next.js dev overlay فيغطي الشاشة.
 *
 * الإصلاح: النمط الصحيح `inert={cond || undefined}` — يحافظ على عزل DOM
 * (D-115/rendering-integrity) بلا أي تحذير.
 *
 * القاعدة الدائمة: `inert` boolean-only في كل الواجهة — ممنوع أي صيغة نصية.
 *
 * تشغيل: node frontend/tests/iss120_inert_boolean_attribute.test.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const appDir = resolve(__dirname, '..', 'app');

let failed = 0;
const check = (name, cond, detail = '') => {
    if (cond) {
        console.log(`  ✅ ${name}`);
    } else {
        failed += 1;
        console.error(`  ❌ ${name}${detail ? ` — ${detail}` : ''}`);
    }
};

// ─── مسح كل ملفات الواجهة بحثاً عن أي inert نصية ─────────────────────────────
const walk = (dir) => {
    const out = [];
    for (const entry of readdirSync(dir)) {
        const p = join(dir, entry);
        const st = statSync(p);
        if (st.isDirectory()) out.push(...walk(p));
        else if (/\.(jsx?|tsx?)$/.test(entry)) out.push(p);
    }
    return out;
};

console.log('ISS-120 (D-153) — inert boolean attribute:');

const stringInertRe = /inert=\{[^}]*['"](?:true|false)['"]/;
const offenders = [];
for (const file of walk(appDir)) {
    const src = readFileSync(file, 'utf-8');
    if (stringInertRe.test(src)) offenders.push(file);
}
check('no string-form inert anywhere in frontend/app', offenders.length === 0, offenders.join(', '));

// ─── الملف المُصاب تحديداً: النمط الصحيح موجود ───────────────────────────────
const cogniforge = readFileSync(
    resolve(appDir, 'components', 'CogniForgeApp.jsx'),
    'utf-8',
);
check(
    'agent sidebar uses boolean inert (cond || undefined)',
    cogniforge.includes('inert={!isAgentSidebarOpen || undefined}'),
);
check(
    'conversations sidebar uses boolean inert (cond || undefined)',
    cogniforge.includes('inert={!isSidebarOpen || undefined}'),
);
check(
    'DOM-exclusion (rendering integrity) preserved — inert still present on both sidebars',
    (cogniforge.match(/inert=\{/g) || []).length >= 2,
);

if (failed > 0) {
    console.error(`\n${failed} ISS-120 check(s) failed`);
    process.exit(1);
}
console.log('\n🎉 all ISS-120 inert checks pass');
