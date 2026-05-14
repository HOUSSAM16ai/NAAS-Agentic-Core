import "./globals.css";
// ISS-063 (D-055.2): legacy-style.css حُذف بالكامل من الـ import والـ filesystem.
import 'katex/dist/katex.min.css';

export const metadata = {
  title: "CogniForge Next Gateway",
  description: "Next.js shell for the CogniForge legacy UI."
};

// ISS-066 (D-058): Anti-flash theme script — يُنفَّذ synchronously قبل أي render.
// يقرأ الـ theme من localStorage ويُطبِّقه على html فوراً لتجنب
// الوميض البصري (FOUC) عند التحميل الأولي أو عند refresh.
// يُطبَّق على: html.dataset.theme + html.style.colorScheme + body.dataset.theme.
const themeScript = `(function(){try{var t=localStorage.getItem('theme')||'dark';var r=document.documentElement;r.dataset.theme=t;r.style.colorScheme=t;if(document.body){document.body.dataset.theme=t;}else{var o=new MutationObserver(function(){if(document.body){document.body.dataset.theme=t;o.disconnect();}});o.observe(r,{childList:true});}}catch(e){}})();`;

export default function RootLayout({ children }) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <head>
        {/* ISS-066: script يُنفَّذ قبل hydration لتجنب FOUC في light mode */}
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
