/**
 * قراءة أخطاء الـAPI بالعربية — المصدر الوحيد (D-236 · ISS-152).
 *
 * ## العطب الذي وُلدت منه هذه الوحدة
 *
 * كانت كل شاشات الدخول تكتب:
 *
 *     setError((await res.json()).detail || 'Login failed');
 *
 * والخلفية لم تُخرج مفتاح `detail` **قطّ** — كانت تُخرج `message`. فكان `.detail`
 * يساوي `undefined` دائماً، ويُعرَض السقوط الحرفي **`Login failed`**: سلسلة
 * إنجليزية على منصّة عربية، تُخفي السبب الحقيقي أيّاً كان (401 · 429 · 422 · 500).
 *
 * قِيس حيّاً على خادم حقيقي قبل الإصلاح:
 *
 *     POST /api/security/login -> 401
 *     TOP-LEVEL KEYS: ['data', 'message', 'status', 'timestamp']
 *     HAS 'detail' KEY: False
 *     ==> FRONTEND WOULD DISPLAY: 'Login failed'
 *
 * ## القواعد
 *
 * 1. **الترجمة بالرمز لا بالنصّ.** `error_code` مستقرّ؛ مطابقة النصّ الإنجليزي
 *    تنكسر بأوّل إعادة صياغة في الخادم.
 * 2. **رسالة الخادم أوّلاً حين تكون مفيدة.** الخادم يعرف تفاصيل لا نعرفها هنا؛
 *    الجدول أدناه سقوطٌ حين لا يقول شيئاً مفهوماً للطالب.
 * 3. ⛔ **لا سلسلة إنجليزية تصل الطالب.** الغياب يُعلَن بالعربية.
 */

export const ARABIC_BY_ERROR_CODE = {
  unauthorized: 'البريد الإلكتروني أو كلمة المرور غير صحيحة.',
  forbidden: 'لا تملك صلاحية الوصول إلى هذه الصفحة.',
  not_found: 'الصفحة أو المورد غير موجود.',
  conflict: 'هذا البريد الإلكتروني مسجَّل بالفعل.',
  validation_error: 'تحقّق من البيانات المُدخَلة ثمّ أعد المحاولة.',
  account_locked: 'الحساب مقفل مؤقّتاً. حاول بعد قليل.',
  rate_limited: 'محاولات كثيرة في وقت قصير. انتظر قليلاً ثمّ أعد المحاولة.',
  internal_error: 'حدث خطأ في الخادم. حاول مرّة أخرى بعد قليل.',
  upstream_error: 'الخدمة غير متاحة مؤقّتاً. حاول بعد قليل.',
  service_unavailable: 'الخدمة غير متاحة مؤقّتاً. حاول بعد قليل.',
  upstream_timeout: 'استغرق الخادم وقتاً أطول من المتوقّع. حاول مرّة أخرى.',
};

export const ARABIC_BY_STATUS = {
  400: 'طلب غير صالح. تحقّق من البيانات المُدخَلة.',
  401: 'البريد الإلكتروني أو كلمة المرور غير صحيحة.',
  403: 'لا تملك صلاحية الوصول إلى هذه الصفحة.',
  404: 'الصفحة أو المورد غير موجود.',
  409: 'هذا البريد الإلكتروني مسجَّل بالفعل.',
  422: 'تحقّق من البيانات المُدخَلة ثمّ أعد المحاولة.',
  429: 'محاولات كثيرة في وقت قصير. انتظر قليلاً ثمّ أعد المحاولة.',
  500: 'حدث خطأ في الخادم. حاول مرّة أخرى بعد قليل.',
  502: 'الخدمة غير متاحة مؤقّتاً. حاول بعد قليل.',
  503: 'الخدمة غير متاحة مؤقّتاً. حاول بعد قليل.',
  504: 'استغرق الخادم وقتاً أطول من المتوقّع. حاول مرّة أخرى.',
};

/**
 * بحثٌ آمن في جدول ترجمة.
 *
 * ⚠️ `TABLE[key]` وحدها **معطوبة**: مفاتيح سلسلة النماذج الأولية موجودة على كل
 * كائن، فـ`error_code: "constructor"` يُرجع **دالّة** لا نصّاً، و`"toString"`
 * كذلك. القيمة تمرّ فحص `if (byCode)` لأنها صادقة، فتصل طبقة العرض كائناً —
 * وتُسقِط شاشة الطالب أو تعرض `function Object() { [native code] }`.
 *
 * وهذا بالضبط صنف العطب الذي يعالجه هذا الـPR: مسار خطأ يفشل أمام الطالب.
 */
function lookup(table, key) {
  if (typeof key !== 'string') return undefined;
  return Object.prototype.hasOwnProperty.call(table, key) ? table[key] : undefined;
}

/** هل النصّ صالح للعرض على طالب عربي؟ */
function isPresentable(value) {
  if (typeof value !== 'string') return false;
  const trimmed = value.trim();
  if (!trimmed) return false;
  // رسائل الخادم التقنية الإنجليزية لا تُعرَض — لها ترجمة بالرمز.
  if (/^internal server error$/i.test(trimmed)) return false;
  if (/^validation error$/i.test(trimmed)) return false;
  return true;
}

/**
 * يستخرج رسالة خطأ عربية من استجابة فاشلة.
 *
 * @param {Response} res استجابة `fetch` غير الناجحة.
 * @param {string} fallback رسالة عربية تُعرَض حين لا يقول الخادم شيئاً مفهوماً.
 * @returns {Promise<string>} رسالة جاهزة للعرض — عربية دائماً.
 */
/** يقرأ جسم الاستجابة كـJSON، أو `null` إن لم يكن JSON. */
async function parseJsonBody(res) {
  try {
    const body = await res.json();
    return body && typeof body === 'object' ? body : null;
  } catch (_) {
    // جسمٌ غير JSON (صفحة خطأ من وسيط مثلاً).
    return null;
  }
}

/**
 * يختار الرسالة من جسمٍ مُحلَّل: الرمز أوّلاً، ثمّ نصّ الخادم إن كان مفهوماً.
 *
 * `detail` هو العقد القياسي و`message` توافقٌ تاريخي — كلاهما يُقرأ لأن نسخة
 * خادم أقدم قد تُرسل واحداً دون الآخر، والواجهة لا تُسقِط الطالب لأن الخادم
 * لم يُحدَّث بعد.
 */
function messageFromBody(body) {
  const byCode = lookup(ARABIC_BY_ERROR_CODE, body.error_code);
  if (byCode) return byCode;
  if (isPresentable(body.detail)) return body.detail;
  if (isPresentable(body.message)) return body.message;
  return null;
}

export async function readApiError(res, fallback = 'حدث خطأ غير متوقّع.') {
  const body = await parseJsonBody(res);
  const fromBody = body ? messageFromBody(body) : null;
  return fromBody || lookup(ARABIC_BY_STATUS, String(res.status)) || fallback;
}

export default readApiError;
