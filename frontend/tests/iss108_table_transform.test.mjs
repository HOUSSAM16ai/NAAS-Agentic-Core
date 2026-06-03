// ISS-108 (D-097) Fix 5 — Markdown table → readable lines (no remark-gfm).
// المشروع لا يستخدم remark-gfm، فجداول `|...|` كانت تُعرض خاماً (جزء من «النصوص
// الغبية»). `preprocessMath.convertMarkdownTables` يحوّلها لعنوان عريض + نقاط.
//
// تشغيل: node frontend/tests/iss108_table_transform.test.mjs
import { preprocessMath } from '../app/utils/preprocessMath.js';

let pass = 0;
let fail = 0;
function check(name, cond) {
    if (cond) {
        pass++;
        console.log('  ✅ ' + name);
    } else {
        fail++;
        console.log('  ❌ ' + name);
    }
}

// 1) جدول pedagogical نموذجي (من إخراج LLM الحقيقي)
const tableSrc =
    '## تمهيد\n\n' +
    '| المرحلة | ما نفعله |\n' +
    '|--------|----------|\n' +
    '| **1- الفهم** | نحدد المطلوب |\n' +
    '| **2- الأدوات** | نختار القانون $C(n,k)$ |\n\n' +
    'نكمل.';
const out = preprocessMath(tableSrc);
check('no raw table pipes remain', (out.match(/\|/g) || []).length === 0);
check('header becomes bold line', out.includes('**المرحلة — ما نفعله**'));
check('rows become bullets', out.includes('- **1- الفهم** — نحدد المطلوب'));
check('inline LaTeX preserved', out.includes('$C(n,k)$'));
check('surrounding text intact', out.includes('## تمهيد') && out.includes('نكمل.'));

// 2) النص بلا جداول لا يتغيّر (عدا تحويلات LaTeX المعتادة)
const plain = 'شرح بسيط بلا جداول. النتيجة $$P(A)=\\frac{14}{165}$$';
const outPlain = preprocessMath(plain);
check('plain text unaffected', outPlain.includes('شرح بسيط بلا جداول'));

// 3) قيمة مطلقة في الرياضيات `$|x|$` خارج كتلة جدول لا تُعامَل كجدول
const absVal = 'القيمة المطلقة $|x|$ معروفة.';
const outAbs = preprocessMath(absVal);
check('math abs-value line not treated as table', outAbs.includes('$|x|$'));

console.log(`\nISS-108 table transform: ${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);
