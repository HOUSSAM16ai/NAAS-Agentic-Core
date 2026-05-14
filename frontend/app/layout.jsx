import "./globals.css";
// ISS-063 (D-055.2): legacy-style.css حُذف بالكامل من الـ import والـ filesystem.
//   كان يفرض gradient ذهبي + ألوان ذهبية warm/cream تطغى على نظام D-055 الفاخر:
//     - radial-gradient(1200px, rgba(212,175,55,0.16)) على body — تدرُّج ذهبي
//     - radial-gradient(900px, rgba(0,170,255,0.12)) — تدرُّج أزرق
//     - --primary-color: #d4af37 (ذهبي)
//     - --background-color: #050506 (ليس pure-black)
//     - --text-color: #f7f3ec (cream، ليس أبيض فاخر)
//     - --border-color: rgba(212,175,55,0.28) (حدود ذهبية)
//   globals.css يُغطِّي الآن كل class selectors التي كان يستخدمها legacy.
import 'katex/dist/katex.min.css';

export const metadata = {
  title: "CogniForge Next Gateway",
  description: "Next.js shell for the CogniForge legacy UI."
};

export default function RootLayout({ children }) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
