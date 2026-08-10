/**
 * التدوير الصامت لجلسة الطالب (D-236 · ISS-152).
 *
 * ## لماذا وُجد هذا الملفّ
 *
 * قاعدة الإنتاج قالت الحقيقة صراحةً: **135 رمز تحديث صدر، و135 عائلة** — أي
 * `families == tokens` بالضبط، وهو تعريفُ **صفر تدوير**. كل دخولٍ كان يفتح
 * عائلةً جديدة، ولم يستدعِ أحدٌ `/api/v1/auth/refresh` قطّ، لأن الواجهة كانت
 * تُهمل `refresh_token` من الاستجابة أصلاً. فالباب الثاني موجودٌ ومختبَر
 * ومكشوفٌ في العقد — ولا أحد يعرفه.
 *
 * ونتيجةُ ذلك أنّ عمر رمز الوصول صار **هو** عمر الجلسة: تنتهي صلاحيته فيُطرَد
 * الطالب إلى صفحة الدخول في منتصف تمرين. وقد ضاعف توحيدُ الدخول على
 * `AuthService` هذا الألم — رمزه أقصر عمراً (وأصحّ أمنياً) من الرمز القديم ذي
 * الأربع والعشرين ساعة — فصار **إصلاحُ التدوير شرطاً** لا تحسيناً.
 *
 * ## القوانين التي يفرضها هذا الملفّ
 *
 * 1. **الرمز القصير + التدوير أأمن من الرمز الطويل.** الحلّ ليس إطالة العمر
 *    (رمزٌ مسروق يبقى صالحاً ٢٤ ساعة) بل تجديده قبل انتهائه.
 * 2. **يُجدَّد قبل الانتهاء بهامش، لا عند 401.** الانتظار حتى الرفض يعني أن
 *    الطالب رأى العطب فعلاً — والتجديد الاستباقي يجعله غير مرئي.
 * 3. **الفشل يُميَّز**: رفضٌ قاطع (401/403 — العائلة أُبطلت أو الرمز انتهى) ⇒
 *    خروجٌ صريح. عطبٌ عابر (شبكة · 5xx) ⇒ **إعادة محاولة**، لا طرد. طردُ طالبٍ
 *    بسبب انقطاعٍ لحظي هو بالضبط عطب D-WS-KICK-001 في ثوبٍ جديد.
 * 4. **بلا حالةٍ عامّة**: الوحدة دوالُّ نقيّة + مُجدوِلٌ يُلغى. تُختبَر بلا
 *    متصفّح وبلا React.
 */

/** الهامش قبل الانتهاء (ثانية): يُجدَّد الرمز قبل موته بدقيقتين. */
export const REFRESH_MARGIN_SECONDS = 120;

/** أدنى تأخير قبل التجديد (مللي ثانية) — يمنع حلقةً محمومة على رمزٍ منتهٍ. */
export const MIN_REFRESH_DELAY_MS = 1000;

/** أقصى تأخير (مللي ثانية) — `setTimeout` يفيض فوق ~24.8 يوماً فيُطلق فوراً. */
export const MAX_REFRESH_DELAY_MS = 6 * 60 * 60 * 1000;

/** مهلة نداء التجديد. انتظارٌ مفتوح على حدّ خدمة يحوّل البطء إلى تعليق (D-189). */
export const REFRESH_TIMEOUT_MS = 10000;

/**
 * يقرأ `exp` من حمولة JWT **بلا التحقّق من التوقيع**.
 *
 * ⚠️ للتوقيت فقط. الواجهة لا تملك المفتاح ولا يجوز أن تبني عليه قراراً أمنياً —
 * الخادم هو الحَكَم الوحيد على صلاحية الرمز. أسوأُ ما يفعله رمزٌ مُلفَّق هنا هو
 * أن يُجدَّد باكراً أو متأخّراً، ثمّ يبتّ الخادم.
 *
 * @param {string} token
 * @returns {number|null} `exp` بالثواني منذ الحقبة، أو `null` إن تعذّرت القراءة.
 */
export function readTokenExpiry(token) {
    if (typeof token !== 'string') return null;
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    try {
        // base64url ⇒ base64: الرمز يستعمل `-`/`_` ولا يحمل حشواً.
        const b64 = parts[1].replace(/-/g, '+').replace(/_/g, '/');
        const padded = b64 + '='.repeat((4 - (b64.length % 4)) % 4);
        const json = typeof atob === 'function'
            ? atob(padded)
            : Buffer.from(padded, 'base64').toString('binary');
        const claims = JSON.parse(json);
        const exp = claims && claims.exp;
        return typeof exp === 'number' && Number.isFinite(exp) ? exp : null;
    } catch (_e) {
        return null;
    }
}

/**
 * كم ننتظر قبل التجديد.
 *
 * @param {string} token
 * @param {number} [nowMs] الآن بالمللي ثانية (يُحقَن في الاختبار).
 * @returns {number|null} التأخير بالمللي ثانية، أو `null` إن لم يكن للرمز `exp`
 *   (فلا نجدول شيئاً بدل أن نخمّن — الغياب لا يعني الغموض، D-206/L11).
 */
export function computeRefreshDelay(token, nowMs = Date.now()) {
    const exp = readTokenExpiry(token);
    if (exp === null) return null;
    const target = exp * 1000 - REFRESH_MARGIN_SECONDS * 1000;
    const delay = target - nowMs;
    if (delay < MIN_REFRESH_DELAY_MS) return MIN_REFRESH_DELAY_MS;
    return Math.min(delay, MAX_REFRESH_DELAY_MS);
}

/**
 * هل يعني رمز الحالة أنّ الجلسة **انتهت قطعاً**؟
 *
 * 401/403 وحدهما. وكل ما عداهما (شبكة · 5xx · 429) عطبٌ عابر: يُعاد المحاولة
 * ولا يُطرَد الطالب. هذا هو نفس تمييز D-WS-KICK-001 مطبَّقاً على مسار التدوير.
 *
 * @param {number|null} status
 * @returns {boolean}
 */
export function isTerminalAuthFailure(status) {
    return status === 401 || status === 403;
}

/**
 * ينفّذ دورة تدوير واحدة.
 *
 * @param {object} opts
 * @param {string} opts.refreshToken
 * @param {(path: string) => string} opts.apiUrl
 * @param {typeof fetch} [opts.fetchImpl]
 * @returns {Promise<{ok: true, tokens: {access_token: string, refresh_token: string}}
 *   | {ok: false, terminal: boolean, status: number|null}>}
 */
export async function rotateSession({ refreshToken, apiUrl, fetchImpl }) {
    const doFetch = fetchImpl || (typeof fetch === 'function' ? fetch : null);
    if (!doFetch || typeof refreshToken !== 'string' || refreshToken.length === 0) {
        return { ok: false, terminal: true, status: null };
    }

    // مهلة صريحة: `AbortController` حيث توفّر، وإلّا نمضي بلا مهلة بدل السقوط.
    let signal;
    let timer = null;
    if (typeof AbortController === 'function') {
        const controller = new AbortController();
        signal = controller.signal;
        timer = setTimeout(() => controller.abort(), REFRESH_TIMEOUT_MS);
    }

    try {
        const res = await doFetch(apiUrl('/api/v1/auth/refresh'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
            ...(signal ? { signal } : {}),
        });
        if (!res.ok) {
            return { ok: false, terminal: isTerminalAuthFailure(res.status), status: res.status };
        }
        const tokens = await res.json();
        if (!tokens || typeof tokens.access_token !== 'string' || tokens.access_token === '') {
            // 200 بجسمٍ لا يحمل رمزاً: عطبٌ في الخادم لا انتهاءُ جلسة.
            return { ok: false, terminal: false, status: res.status };
        }
        return { ok: true, tokens };
    } catch (_e) {
        // شبكة · إلغاءٌ بالمهلة · جسمٌ غير JSON — كلّها عابرة بحكم التصنيف.
        return { ok: false, terminal: false, status: null };
    } finally {
        if (timer !== null) clearTimeout(timer);
    }
}
