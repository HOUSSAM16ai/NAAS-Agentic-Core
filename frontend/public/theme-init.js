// ISS-066 (D-058 rev4): Anti-flash theme initializer.
// ملف خارجي يُحمَّل عبر <script src> في <head> — يُنفَّذ synchronously
// قبل أي CSS paint وقبل React hydration.
// هذا هو الطريق الوحيد الموثوق في Next.js 16 App Router لتجنب FOUC.
(function () {
  try {
    var t = localStorage.getItem('theme') || 'dark';
    var r = document.documentElement;
    r.dataset.theme = t;
    r.style.colorScheme = t;
    if (document.body) {
      document.body.dataset.theme = t;
    } else {
      var o = new MutationObserver(function () {
        if (document.body) {
          document.body.dataset.theme = t;
          o.disconnect();
        }
      });
      o.observe(r, { childList: true });
    }
  } catch (e) {}
})();
