/**
 * ISS-152 (D-236) — عقد أخطاء الـAPI على جانب الواجهة.
 *
 * الطالب كان يرى `Login failed` — سلسلة إنجليزية حرفية على منصّة عربية — لأن
 * الخلفية تُخرج `message` والواجهة تقرأ `detail`. مُبرهَنٌ حيّاً قبل الإصلاح:
 * `HAS 'detail' KEY: False` على 401 حقيقي.
 *
 * ويضيف هذا الملفّ عقداً ثانياً رصدته مراجعة CodeRabbit وكان **عطباً حقيقياً**:
 * `TABLE[key]` تقرأ سلسلة النماذج الأولية، فـ`error_code: "constructor"` يُرجع
 * **دالّة** لا نصّاً، وتمرّ فحص الصدق فتصل طبقة العرض. أي أن مسار الخطأ نفسه —
 * الذي وُجد ليشرح للطالب ما جرى — كان قادراً على إسقاط شاشته.
 *
 * تشغيل: node frontend/tests/iss152_api_error_contract.test.mjs
 */

import { readFileSync } from 'node:fs';
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

const { readApiError, ARABIC_BY_ERROR_CODE, ARABIC_BY_STATUS } = await import(
    resolve(repoRoot, 'frontend/app/utils/apiError.js')
);

/** استجابة `fetch` مُصغَّرة. */
const response = (status, body, { json = true } = {}) => ({
    status,
    json: async () => {
        if (!json) throw new SyntaxError('Unexpected token < in JSON');
        return body;
    },
});

console.log('\nISS-152 — API error contract (frontend)');

// ── 1) الجذر: العقد يُقرأ فعلاً ─────────────────────────────────────────────
{
    const msg = await readApiError(
        response(401, {
            status: 'error',
            detail: 'Invalid email or password',
            message: 'Invalid email or password',
            error_code: 'unauthorized',
        }),
        'سقوط',
    );
    check(
        '401 يُترجَم بالرمز إلى العربية',
        msg === ARABIC_BY_ERROR_CODE.unauthorized,
        `got: ${msg}`,
    );
    check('لا تظهر السلسلة الإنجليزية الحرفية', msg !== 'Login failed');
}

// ── 2) ⛔ العطب الحقيقي: مفاتيح سلسلة النماذج الأولية ────────────────────────
for (const poisoned of ['constructor', 'toString', 'valueOf', 'hasOwnProperty']) {
    const msg = await readApiError(response(500, { error_code: poisoned }), 'سقوط عربي');
    check(
        `error_code="${poisoned}" لا يُرجع دالّة`,
        typeof msg === 'string',
        `typeof = ${typeof msg}`,
    );
    check(
        `error_code="${poisoned}" يسقط إلى رسالة الحالة`,
        msg === ARABIC_BY_STATUS[500],
        `got: ${String(msg).slice(0, 60)}`,
    );
}

// ── 3) جسمٌ غير JSON لا يُسقِط الواجهة ───────────────────────────────────────
{
    const msg = await readApiError(response(502, null, { json: false }), 'سقوط عربي');
    check('جسم غير JSON يسقط إلى رسالة الحالة', msg === ARABIC_BY_STATUS[502], `got: ${msg}`);
}

// ── 4) رسالة الخادم التقنية لا تصل الطالب ───────────────────────────────────
{
    const msg = await readApiError(
        response(500, { detail: 'Internal Server Error', message: 'Internal Server Error' }),
        'سقوط عربي',
    );
    check('«Internal Server Error» تُترجَم ولا تُعرَض حرفياً', msg === ARABIC_BY_STATUS[500]);
}

// ── 5) كل قيمة معروضة عربية ────────────────────────────────────────────────
{
    const arabic = /[؀-ۿ]/;
    const values = [...Object.values(ARABIC_BY_ERROR_CODE), ...Object.values(ARABIC_BY_STATUS)];
    check(
        `كل رسائل الجدولين عربية (${values.length} رسالة)`,
        values.every((v) => arabic.test(v)),
        values.filter((v) => !arabic.test(v)).join(' | '),
    );
}

// ── 6) المرآتان تحملان نفس الجدولين ────────────────────────────────────────
// النسخة الكاملة من هذا الفحص في `scripts/fitness/check_error_contract_parity.py`
// (تقارن المفاتيح والقيم). هنا نتحقّق فقط من أنّ البحث الآمن موجود في المرآتين،
// فالعطب أعلاه كان مكرَّراً ثلاث مرّات لأنه نُسخ ثلاث مرّات.
for (const mirror of ['frontend/public/js/legacy-app.jsx', 'app/static/js/legacy-app.jsx']) {
    const src = readFileSync(resolve(repoRoot, mirror), 'utf8');
    check(`${mirror}: يستعمل البحث الآمن`, src.includes('hasOwnProperty.call'));
    check(
        `${mirror}: لا بحث مباشر غير محروس`,
        !src.includes('ARABIC_BY_ERROR_CODE[body.error_code]'),
    );
}

console.log(failed === 0 ? '\n✅ ISS-152 frontend contract: all passed\n' : `\n❌ ${failed} failed\n`);
process.exit(failed === 0 ? 0 : 1);
