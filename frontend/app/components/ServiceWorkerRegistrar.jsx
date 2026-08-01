"use client";

import { useEffect } from "react";

/**
 * تسجيل عامل الخدمة (D-199).
 *
 * ملفٌّ في `public/` بلا تسجيل هو كودٌ ميّت — قانون «لا ZOMBIE» ينطبق على الواجهة
 * كما ينطبق على الخادم. هذا المكوّن هو المستهلك الحيّ.
 *
 * التسجيل **بعد `load`**: التسجيل أثناء التحميل ينافس أصول الصفحة الحرجة على نطاقٍ
 * ضيّق أصلاً، فيؤخّر ما جاء المستخدم لأجله كي يُسرّع الزيارة التالية.
 */
export default function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;
    // بيئة التطوير: عامل الخدمة يُخبّئ حزماً تتغيّر كلّ ثانية فيُربك التطوير.
    if (process.env.NODE_ENV !== "production") return;

    const register = () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // التسجيل الفاشل لا يُبلَّغ للمستخدم: التطبيق يعمل بدونه تماماً.
      });
    };

    if (document.readyState === "complete") {
      register();
      return undefined;
    }
    window.addEventListener("load", register);
    return () => window.removeEventListener("load", register);
  }, []);

  return null;
}
