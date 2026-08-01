"use client";

import { useEffect, useState } from "react";
import CogniForgeApp from "./components/CogniForgeApp";

/**
 * D-199: قشرة تُرسَم قبل الترطيب بدل صفحةٍ بيضاء.
 *
 * كان `if (!mounted) return null;` يعني أنّ أوّل رسمٍ **فارغ تماماً**: على شبكة 3G يرى
 * الطالب بياضاً طوال تحميل الحزمة وتنفيذها قبل ظهور أيّ شيء — أسوأ ما يمكن فعله بأبطأ
 * اتصال، وهو اتصال معظم مستخدمينا. الحارس نفسه ما زال لازماً (`CogniForgeApp` يقرأ
 * `window`/`localStorage` عند البناء فيكسر تصييرُه على الخادم الترطيبَ)، لكنّ البديل
 * عنه ليس العدم: قشرةٌ ساكنة بنفس الورق والبنية تجعل الانتقال بلا وميض.
 */
export default function ClientOnlyApp() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="app-shell" aria-busy="true" aria-live="polite">
        <span className="app-shell__brand">CogniForge</span>
        <p className="app-shell__hint">جارٍ تحضير مساحة المذاكرة…</p>
      </div>
    );
  }

  return <CogniForgeApp />;
}
