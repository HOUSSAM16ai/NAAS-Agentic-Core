/* eslint-disable no-restricted-globals */
/**
 * عامل الخدمة — قشرةٌ تعمل بلا شبكة (D-199).
 *
 * لماذا هذا موجود
 * ───────────────
 * طلابنا على 3G متقطّع: القطار، سطح المنزل، انقطاع الرصيد. بلا عامل خدمة، كلّ انقطاعٍ
 * لحظي يُنتِج صفحة ديناصور المتصفّح ويُنهي جلسة المذاكرة. القشرة المُخبَّأة تعني أنّ
 * التطبيق **يفتح** دائماً ويشرح حالته.
 *
 * قواعد دائمة
 * ───────────
 * 1. **لا تُخبَّأ طلبات التنقّل خارج القشرة، ولا أيّ استجابة API.** جواب معلّمٍ قديم
 *    أسوأ من رسالة «لا اتصال»: الطالب لا يملك وسيلة ليعرف أنّه قديم.
 * 2. **الشبكة أوّلاً للتنقّل**، والقشرة احتياطٌ عند الفشل فقط — فلا يرى الطالب نسخةً
 *    قديمة من التطبيق بعد نشر إصدار جديد.
 * 3. **لا يُخبَّأ إلّا 200 من نفس الأصل**: تخبئة إعادة توجيهٍ أو خطأ تُثبِّت العطب.
 * 4. الإصدار في اسم المخزن؛ تغييرُه ينظّف كلّ ما سبق عند التفعيل.
 */

const VERSION = "cogniforge-v1";
const SHELL_CACHE = `${VERSION}-shell`;
const OFFLINE_URL = "/offline.html";

const SHELL_ASSETS = [
  OFFLINE_URL,
  "/manifest.webmanifest",
  "/icons/icon.svg",
  "/icons/icon-maskable.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      // `Promise.allSettled`: أصلٌ واحد مفقود يجب ألّا يمنع تثبيت العامل كلّه.
      .then((cache) =>
        Promise.allSettled(SHELL_ASSETS.map((asset) => cache.add(asset))),
      )
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key.startsWith("cogniforge-") && key !== SHELL_CACHE)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // قاعدة ١: لا تُلمَس واجهات البيانات إطلاقاً — لا تخبئة ولا اعتراض.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/ws")) return;

  if (request.mode === "navigate") {
    // قاعدة ٢: الشبكة أوّلاً؛ القشرة عند الفشل فقط.
    event.respondWith(
      fetch(request).catch(() =>
        caches.match(OFFLINE_URL).then((cached) => cached || Response.error()),
      ),
    );
    return;
  }

  // أصول ثابتة: من المخزن إن وُجدت، وإلّا من الشبكة مع تخبئة النسخة الصالحة.
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request)
        .then((response) => {
          // قاعدة ٣: 200 من نفس الأصل فقط.
          if (!response || response.status !== 200 || response.type !== "basic") {
            return response;
          }
          const copy = response.clone();
          caches.open(SHELL_CACHE).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => cached || Response.error());
    }),
  );
});
