import "./globals.css";
// ISS-063 (D-055.2): legacy-style.css حُذف بالكامل من الـ filesystem.
import 'katex/dist/katex.min.css';

export const metadata = {
  title: "CogniForge Next Gateway",
  description: "Next.js shell for the CogniForge legacy UI."
};

// ISS-066 (D-058 rev4): Anti-flash theme script عبر ملف خارجي في /public.
// Next.js 16 App Router يُنقِل <script dangerouslySetInnerHTML> من <head> إلى <body>
// و next/script beforeInteractive يُنفَّذ عبر __next_s payload (بعد runtime).
// الحل الوحيد الموثوق: <script src="/theme-init.js"> في <head> — يُنفَّذ
// synchronously قبل أي CSS paint وقبل React hydration.

export default function RootLayout({ children }) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <head>
        {/* ISS-066 rev4: src script في <head> — يُنفَّذ synchronously قبل hydration */}
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script src="/theme-init.js" />
      </head>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
