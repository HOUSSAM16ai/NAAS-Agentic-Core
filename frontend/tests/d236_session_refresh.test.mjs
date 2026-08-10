/**
 * D-236 · ISS-152 — التدوير الصامت للجلسة.
 *
 * قاعدة الإنتاج قالت العطب بالأرقام: **135 رمز تحديث و135 عائلة**، أي
 * `families == tokens` — تعريفُ صفر تدوير. الرمز كان يصل الواجهة ويُرمى، فصار
 * عمرُ رمز الوصول هو عمر الجلسة، والعلاج المُطبَّق سابقاً كان **إطالة العمر**:
 * علاجٌ يزيد المرض (رمزٌ مسروق يبقى صالحاً أطول).
 *
 * ⚠️ العقد الذي يحرسه هذا الملفّ ليس «هل يُجدَّد؟» بل **متى لا يُطرَد الطالب**:
 * انقطاعُ شبكةٍ لحظي أو 5xx يجب أن يُعيد المحاولة، لا أن يُلقي الطالب على شاشة
 * الدخول. وهو بالضبط عطب D-WS-KICK-001 لو عُمِّم الفشل.
 *
 * تشغيل: node frontend/tests/d236_session_refresh.test.mjs
 */

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

const {
    readTokenExpiry,
    computeRefreshDelay,
    isTerminalAuthFailure,
    rotateSession,
    REFRESH_MARGIN_SECONDS,
    MIN_REFRESH_DELAY_MS,
    MAX_REFRESH_DELAY_MS,
} = await import(resolve(repoRoot, 'frontend/app/utils/sessionRefresh.js'));

/** يبني JWT صالح الشكل (بلا توقيع حقيقي — التوقيت وحده ما يُقرأ هنا). */
const b64url = (obj) =>
    Buffer.from(JSON.stringify(obj)).toString('base64')
        .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
const jwt = (claims) => `${b64url({ alg: 'HS256', typ: 'JWT' })}.${b64url(claims)}.sig`;

const apiUrl = (p) => `http://test${p}`;

console.log('\nD-236 — silent session rotation');

// ── 1) قراءة `exp` ──────────────────────────────────────────────────────────
{
    const exp = Math.floor(Date.now() / 1000) + 3600;
    check('يقرأ exp من رمز سليم', readTokenExpiry(jwt({ exp, sub: '1' })) === exp);
    check('رمزٌ بلا exp يُرجع null', readTokenExpiry(jwt({ sub: '1' })) === null);
    for (const bad of ['', 'not-a-jwt', 'a.b', 'a.b.c.d', null, undefined, 42, {}]) {
        check(`مُدخَل فاسد (${JSON.stringify(bad)}) يُرجع null`, readTokenExpiry(bad) === null);
    }
    check('حمولة غير base64 لا تُسقِط الدالّة', readTokenExpiry('x.@@@@.y') === null);
}

// ── 2) الجدولة: قبل الانتهاء بهامش، لا عنده ─────────────────────────────────
{
    const now = 1_000_000_000_000; // مللي ثانية ثابتة — لا اعتماد على الساعة
    const exp = Math.floor(now / 1000) + 3600;
    const delay = computeRefreshDelay(jwt({ exp }), now);
    const expected = 3600_000 - REFRESH_MARGIN_SECONDS * 1000;
    check(`رمزٌ عمره ساعة ⇒ تجديدٌ بعد ${expected / 1000}s`, delay === expected, `got ${delay}`);
    check(
        'التجديد يسبق الانتهاء فعلاً',
        delay < exp * 1000 - now,
        'وإلّا رأى الطالبُ الانتهاء قبل التجديد',
    );
}
{
    // ⛔ الحالة التي تُنتج حلقةً محمومة لو لم تُحرَس: رمزٌ منتهٍ أو شبه منتهٍ.
    const now = 1_000_000_000_000;
    for (const secs of [-3600, -1, 0, 60, REFRESH_MARGIN_SECONDS]) {
        const d = computeRefreshDelay(jwt({ exp: Math.floor(now / 1000) + secs }), now);
        check(
            `رمزٌ ينتهي بعد ${secs}s ⇒ تأخيرٌ لا يقلّ عن ${MIN_REFRESH_DELAY_MS}ms`,
            d >= MIN_REFRESH_DELAY_MS,
            `got ${d}`,
        );
    }
}
{
    // سقفٌ: `setTimeout` يفيض فوق ~24.8 يوماً فيُطلق **فوراً** — انفجارُ نداءات.
    const now = 1_000_000_000_000;
    const d = computeRefreshDelay(jwt({ exp: Math.floor(now / 1000) + 400 * 24 * 3600 }), now);
    check('عمرٌ خيالي يُقصَّ إلى السقف', d === MAX_REFRESH_DELAY_MS, `got ${d}`);
}
{
    check('بلا exp لا جدولة (null لا صفر)', computeRefreshDelay(jwt({ sub: '1' })) === null);
}

// ── 3) ⛔ العقد الحاسم: أي فشلٍ يطرد الطالب؟ ────────────────────────────────
{
    for (const s of [401, 403]) {
        check(`${s} ⇒ نهائي (الجلسة انتهت قطعاً)`, isTerminalAuthFailure(s) === true);
    }
    for (const s of [0, 408, 429, 500, 502, 503, 504, null, undefined]) {
        check(`${s} ⇒ عابر (لا طرد)`, isTerminalAuthFailure(s) === false);
    }
}

// ── 4) دورة التدوير الحقيقية عبر fetch مُحاكى ───────────────────────────────
{
    let seen = null;
    const fetchImpl = async (url, opts) => {
        seen = { url, body: JSON.parse(opts.body), method: opts.method };
        return {
            ok: true,
            status: 200,
            json: async () => ({ access_token: 'new-access', refresh_token: 'new-refresh' }),
        };
    };
    const r = await rotateSession({ refreshToken: 'old-refresh', apiUrl, fetchImpl });
    check('التدوير الناجح يُرجع ok', r.ok === true);
    check('يُصيب المسار القانوني', seen.url === 'http://test/api/v1/auth/refresh', seen.url);
    check('يرسل POST', seen.method === 'POST');
    check('يرسل refresh_token بالاسم الذي يقرؤه الخادم', seen.body.refresh_token === 'old-refresh');
    check('يُعيد الرمزين الجديدين', r.tokens.access_token === 'new-access' && r.tokens.refresh_token === 'new-refresh');
    check(
        'الرمز الجديد ليس القديم — أي أنّ العائلة دارت فعلاً',
        r.tokens.refresh_token !== 'old-refresh',
    );
}
{
    const fetchImpl = async () => ({ ok: false, status: 401, json: async () => ({}) });
    const r = await rotateSession({ refreshToken: 'revoked', apiUrl, fetchImpl });
    check('401 ⇒ فشلٌ نهائي', r.ok === false && r.terminal === true);
}
{
    const fetchImpl = async () => ({ ok: false, status: 503, json: async () => ({}) });
    const r = await rotateSession({ refreshToken: 'ok', apiUrl, fetchImpl });
    check('503 ⇒ فشلٌ عابر، الطالب يبقى داخلاً', r.ok === false && r.terminal === false);
}
{
    const fetchImpl = async () => { throw new TypeError('Failed to fetch'); };
    const r = await rotateSession({ refreshToken: 'ok', apiUrl, fetchImpl });
    check('انقطاع الشبكة ⇒ عابر لا طرد', r.ok === false && r.terminal === false);
}
{
    // 200 بجسمٍ بلا رمز: عطبُ خادم لا انتهاءُ جلسة — لا يُطرَد الطالب.
    const fetchImpl = async () => ({ ok: true, status: 200, json: async () => ({}) });
    const r = await rotateSession({ refreshToken: 'ok', apiUrl, fetchImpl });
    check('200 بلا access_token ⇒ عابر لا طرد', r.ok === false && r.terminal === false);
}
{
    const fetchImpl = async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError('x'); } });
    const r = await rotateSession({ refreshToken: 'ok', apiUrl, fetchImpl });
    check('جسمٌ غير JSON ⇒ عابر لا طرد', r.ok === false && r.terminal === false);
}
{
    const r = await rotateSession({ refreshToken: '', apiUrl, fetchImpl: async () => ({ ok: true }) });
    check('بلا رمز تحديث ⇒ نهائي (لا شيء يُدوَّر)', r.ok === false && r.terminal === true);
}

// ── 5) العقد مع الواجهة: الرمز يُحفَظ ويُمحى ────────────────────────────────
{
    const { readFileSync } = await import('node:fs');
    const src = readFileSync(resolve(repoRoot, 'frontend/app/components/CogniForgeApp.jsx'), 'utf8');
    check(
        'الدخول يُمرِّر refresh_token (كان يُرمى — 135 عائلة/135 رمزاً)',
        /onLogin\(\s*data\.access_token\s*,\s*data\.user\s*,\s*data\.refresh_token\s*\)/.test(src),
    );
    check("الرمز يُحفَظ", /localStorage\.setItem\('refresh_token'/.test(src));
    check("والخروج يمحوه — لا يبقى سندٌ لحامله بعد الخروج",
        /localStorage\.removeItem\('refresh_token'\)/.test(src));

    // ⛔ التدوير لا يكتب هوية الطالب.
    //
    // كان مسار النجاح يمرّر `user` المقروء من إغلاق التأثير إلى `handleLogin`.
    // ولو دار الرمز قبل وصول `/me` لكان `null`، فتُستبدَل الجلسة بشاشة الدخول —
    // أي أنّ آلية منع الطرد تطرد. الحارس مربوطٌ بموضع النداء لا بوجود اسمٍ في
    // الملفّ (درسُ فحوص المرآة في `iss152_api_error_contract.test.mjs`).
    check(
        'التدوير يستعمل مُحدِّثاً للرموز وحدها',
        /applyRotatedTokens\(\s*result\.tokens\.access_token\s*,\s*result\.tokens\.refresh_token\s*\)/.test(src),
    );
    check(
        'ولا يمرّ عبر handleLogin (الذي يكتب `user`)',
        !/handleLogin\([^)]*result\.tokens/.test(src),
    );
}

console.log(failed === 0 ? '\n✅ D-236 session rotation: all passed\n' : `\n❌ ${failed} failed\n`);
process.exit(failed === 0 ? 0 : 1);
