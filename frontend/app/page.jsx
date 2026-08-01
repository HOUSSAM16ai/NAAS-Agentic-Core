import ClientOnlyApp from "./ClientOnlyApp";
import IconStylesheet from "./components/IconStylesheet";
import ServiceWorkerRegistrar from "./components/ServiceWorkerRegistrar";

export default function Home() {
  return (
    <main>
      {/* D-199: المستهلك الحيّ لـ`public/sw.js` — ملفٌّ بلا تسجيل كودٌ ميّت. */}
      <ServiceWorkerRegistrar />
      {/* D-199: الأيقونات بعد الترطيب — كانت `@import` تحجب أوّل رسم. */}
      <IconStylesheet />
      <ClientOnlyApp />
    </main>
  );
}
