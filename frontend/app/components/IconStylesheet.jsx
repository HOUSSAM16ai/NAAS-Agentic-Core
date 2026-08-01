"use client";

import { useEffect } from "react";

/**
 * تحميل ورقة أنماط الأيقونات **بعد** الترطيب، بلا حجب أوّل رسم (D-199).
 *
 * كانت `globals.css` تبدأ بـ`@import url('…cdnjs…/font-awesome/…/all.min.css')`:
 * و`@import` يحجب الرسم دائماً، فيدفع الطالب على 3G ثمن رحلة DNS+TLS إلى نطاقٍ ثالث
 * **قبل أن يرى حرفاً واحداً**. والأسوأ أنّ ذلك يشتري كامل الحزمة (solid + regular +
 * brands) لأجل ٤٣ أيقونة.
 *
 * الحقن بعد الترطيب لا يكلّف شيئاً هنا: `ClientOnlyApp` لا يعرض التطبيق قبل الترطيب
 * أصلاً، فالأيقونات تصل مع المحتوى الذي تزيّنه لا بعده.
 *
 * ⚠️ **خطوة وسيطة مقصودة.** الحلّ النهائي استبدال الأيقونات الـ٤٣ بـSVG مضمّن
 * (`docs/frontend/ICON_MIGRATION.md`) فتسقط الحزمة كلّها. هذا الملفّ يزيل الحجب الآن
 * بلا المخاطرة بشحن مسارات SVG خاطئة تُصيّر رموزاً مشوّهة.
 */
const ICON_STYLESHEET =
  "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css";
const LINK_ID = "cogniforge-icon-styles";

export default function IconStylesheet() {
  useEffect(() => {
    if (typeof document === "undefined") return;
    if (document.getElementById(LINK_ID)) return;

    const link = document.createElement("link");
    link.id = LINK_ID;
    link.rel = "stylesheet";
    link.href = ICON_STYLESHEET;
    link.crossOrigin = "anonymous";
    link.referrerPolicy = "no-referrer";
    // فشل التحميل لا يُبلَّغ: الأيقونات زينة، والنصّ يبقى مقروءاً بدونها.
    document.head.appendChild(link);
  }, []);

  return null;
}
