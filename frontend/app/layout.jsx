import { Tajawal } from "next/font/google";

import "./globals.css";
// ISS-063 (D-055.2): legacy-style.css حُذف بالكامل من الـ filesystem.
import 'katex/dist/katex.min.css';

// D-199: الخطّ **مُستضاف ذاتياً وقت البناء** عبر `next/font`.
// كان يُحمَّل بـ`@import` من `fonts.googleapis.com` داخل `globals.css`: نطاقٌ ثالث
// يحجب أوّل رسم (DNS + TLS + CSS + ثمّ ملفّات الخطّ) — أغلى تأخيرٍ منفرد على شبكة 3G،
// وهي شبكة معظم طلابنا. `next/font` يستضيف الملفّات مع التطبيق ويُسبِّق تحميلها ويحقن
// `font-display: swap`، فيبدأ النصّ بالظهور فوراً.
//
// وزنان لا خمسة: كلّ وزنٍ إضافي ملفٌّ إضافي، و«عادي» و«عريض» يكفيان لواجهة قراءة.
const arabic = Tajawal({
  subsets: ["arabic", "latin"],
  weight: ["400", "700"],
  display: "swap",
  preload: true,
  variable: "--font-arabic",
});

export const metadata = {
  title: "CogniForge — مساعد البكالوريا",
  description: "منصّة تعليمية للطلاب الجزائريين المقبلين على شهادة البكالوريا.",
  manifest: "/manifest.webmanifest",
  applicationName: "CogniForge",
  appleWebApp: { capable: true, title: "CogniForge", statusBarStyle: "default" },
  formatDetection: { telephone: false },
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  // يتبع لون الورق في كلّ وضع — شريط المتصفّح جزءٌ من السطح لا إطارٌ غريب عنه.
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbfaf7" },
    { media: "(prefers-color-scheme: dark)", color: "#1a1815" },
  ],
};

// ISS-066 (D-058 rev4): Anti-flash theme script عبر ملف خارجي في /public.
// Next.js 16 App Router يُنقِل <script dangerouslySetInnerHTML> من <head> إلى <body>
// و next/script beforeInteractive يُنفَّذ عبر __next_s payload (بعد runtime).
// الحل الوحيد الموثوق: <script src="/theme-init.js"> في <head> — يُنفَّذ
// synchronously قبل أي CSS paint وقبل React hydration.

export default function RootLayout({ children }) {
  return (
    <html lang="ar" dir="rtl" className={arabic.variable} suppressHydrationWarning>
      <head>
        {/* ISS-066 rev4: src script في <head> — يُنفَّذ synchronously قبل hydration */}
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script src="/theme-init.js" />
      </head>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
