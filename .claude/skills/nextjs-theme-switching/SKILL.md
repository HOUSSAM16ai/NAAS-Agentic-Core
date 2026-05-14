---
name: nextjs-theme-switching
description: >
  Diagnose and fix broken light/dark mode theme switching in Next.js apps.
  Use when: theme toggle has no visual effect, light mode shows dark colors,
  page flashes on refresh, code blocks ignore theme, or CSS variables don't
  apply after switching. Covers anti-flash FOUC prevention, CSS specificity
  for html[data-theme], theme-aware CSS variables, lazy useState pattern,
  and GitHub Action CI for theme contracts.
  Triggers on: "light mode broken", "dark mode not working", "theme toggle broken",
  "FOUC", "flash on refresh", "theme not switching", "data-theme not applying",
  "code blocks wrong color", "theme flicker", "الوضع النهاري معطل",
  "الوضع المظلم لا يعمل", "زر التبديل لا يعمل".
---

# Next.js Theme Switching

> **Core law:** A theme switch is only working when ALL of these are true:
> 1. No flash on page refresh (FOUC-free)
> 2. Every element changes color — including code blocks
> 3. The correct theme loads instantly on first paint, not after hydration

---

## 1. Quick Diagnosis (run first)

```bash
# Check CSS selectors
grep "html\[data-theme" frontend/app/globals.css
# Expected: ≥2 results (one for light, one for dark)

# Check anti-flash script
grep "themeScript\|dangerouslySetInnerHTML" frontend/app/layout.jsx
# Expected: both present

# Check for hard-coded colors in code blocks
grep -A8 "\.markdown-content pre" frontend/app/globals.css | grep "#[0-9a-f]\{6\}"
# Expected: no output (should use var(--pre-bg) instead)

# Check lazy useState
grep "useState(() =>" frontend/app/components/*.jsx
# Expected: present for theme state
```

**Healthy state:**
- `html[data-theme='light']` and `html[data-theme='dark']` both exist in CSS
- `layout.jsx` has a synchronous `<script>` in `<head>` reading `localStorage`
- Code block colors use `var(--pre-bg)` / `var(--code-bg)`, not hex literals
- `useState` for theme uses a lazy initializer, not `useState('dark')`

---

## 2. Root Cause Map

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Theme toggle has no effect | `html[data-theme]` CSS selector missing | Add `html[data-theme='light/dark']` as first selector in theme blocks |
| Flash of wrong theme on refresh | No anti-flash script in `<head>` | Add synchronous script to `layout.jsx` |
| Code blocks stay dark in light mode | Hard-coded hex colors (`#0f172a`) | Replace with `var(--pre-bg)` CSS variable |
| Brief flash before correct theme | `useState('dark')` + `useEffect` pattern | Use lazy `useState(() => localStorage...)` |
| Theme applies to some elements, not all | `body` doesn't inherit from `html` | Set `background`/`color` explicitly on `body` using CSS variables |
| Browser scrollbars ignore theme | Missing `colorScheme` | Set `document.documentElement.style.colorScheme = theme` |

---

## 3. The Four Fixes

### Fix 1 — Anti-flash script in `layout.jsx`

Add a synchronous `<script>` in `<head>`. It runs before React hydration, before any CSS paint.

```jsx
// frontend/app/layout.jsx
const themeScript = `(function(){
  try {
    var t = localStorage.getItem('theme') || 'dark';
    var r = document.documentElement;
    r.dataset.theme = t;
    r.style.colorScheme = t;
    if (document.body) {
      document.body.dataset.theme = t;
    } else {
      var o = new MutationObserver(function() {
        if (document.body) { document.body.dataset.theme = t; o.disconnect(); }
      });
      o.observe(r, { childList: true });
    }
  } catch(e) {}
})();`;

export default function RootLayout({ children }) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
```

**Why `suppressHydrationWarning`:** The script mutates `html.dataset.theme` before React hydrates. Without this prop, React throws a hydration mismatch warning.

---

### Fix 2 — CSS selector specificity

JS sets `data-theme` on `document.documentElement` (the `html` element). CSS must target `html[data-theme]` — not just `[data-theme]`.

```css
/* WRONG — misses html element specificity */
[data-theme='light'],
body[data-theme='light'] { ... }

/* CORRECT — html[data-theme] first, highest specificity */
html[data-theme='light'],
body[data-theme='light'],
[data-theme='light'] {
  --bg-color: #ffffff;
  --text-color: #0a0a0a;
  --pre-bg: #f8f8f8;
  --pre-color: #1e1e1e;
  --code-bg: #f4f4f5;
  --code-color: #18181b;
  /* ... all other variables */
}

html[data-theme='dark'],
body[data-theme='dark'],
[data-theme='dark'] {
  --bg-color: #0a0a0a;
  --text-color: #fafafa;
  --pre-bg: #0f172a;
  --pre-color: #e2e8f0;
  --code-bg: #1e1e2e;
  --code-color: #cdd6f4;
  /* ... all other variables */
}
```

Also split `body, html { ... }` into separate rules so `body` explicitly reads variables from its `html` parent:

```css
html {
  background: var(--bg-color);
  color: var(--text-color);
  transition: background-color 0.3s ease, color 0.3s ease;
}

body {
  background: var(--bg-color);  /* explicit — body doesn't always inherit background */
  color: var(--text-color);
  transition: background-color 0.3s ease, color 0.3s ease;
}
```

---

### Fix 3 — CSS variables for code blocks

Never use hard-coded hex colors for elements that must change with the theme.

```css
/* WRONG */
.markdown-content pre {
  background: #0f172a;   /* always dark */
  color: #e2e8f0;
}

/* CORRECT */
.markdown-content pre {
  background: var(--pre-bg);
  color: var(--pre-color);
  border: 1px solid var(--pre-border);
}

.markdown-content code {
  background: var(--code-bg);
  color: var(--code-color);
  border: 1px solid var(--code-border);
}

/* Reset code inside pre — inherits from pre */
.markdown-content pre code {
  background: transparent;
  color: inherit;
  border: none;
}
```

---

### Fix 4 — Lazy `useState` initializer

```jsx
// WRONG — causes double-render flash
const [theme, setTheme] = useState('dark');
useEffect(() => {
  const stored = localStorage.getItem('theme');
  setTheme(stored === 'light' ? 'light' : 'dark');
}, []);

// CORRECT — reads localStorage on first render, no flash
const [theme, setTheme] = useState(() => {
  if (typeof window === 'undefined') return 'dark'; // SSR guard
  return localStorage.getItem('theme') === 'light' ? 'light' : 'dark';
});
```

The `useEffect` for reading initial theme is no longer needed. Keep only the effect that *applies* the theme to the DOM:

```jsx
useEffect(() => {
  const root = document.documentElement;
  root.dataset.theme = theme;
  root.style.colorScheme = theme;
  if (document.body) document.body.dataset.theme = theme;
  localStorage.setItem('theme', theme);
}, [theme]);
```

---

## 4. Light Mode Luxury Overrides

After fixing the mechanics, add light-mode-specific polish. Use `html[data-theme='light']` scoped rules at the end of the CSS file:

```css
/* Header — subtle separator */
html[data-theme='light'] .header {
  border-bottom: 1px solid var(--border-color);
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.04);
}

/* Input — visible border + focus ring */
html[data-theme='light'] .input-area {
  border: 1.5px solid var(--border-color);
  box-shadow: 0 2px 8px rgb(0 0 0 / 0.05);
}
html[data-theme='light'] .input-area:focus-within {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.10);
}

/* Scrollbar */
html[data-theme='light'] ::-webkit-scrollbar-thumb {
  background: #d4d4d8;
}
html[data-theme='light'] ::-webkit-scrollbar-thumb:hover {
  background: #a1a1aa;
}
```

Read `references/light-mode-overrides.md` for the full list of recommended overrides.

---

## 5. GitHub Action CI

Add `.github/workflows/frontend-theme-ci.yml` to enforce theme contracts on every PR touching `frontend/`.

Read `references/github-action-template.md` for the complete 5-job workflow template.

**Critical jobs:**
- `theme-contracts` — verifies `html[data-theme]` selectors and CSS variables exist
- `anti-flash-gate` — verifies anti-flash script and lazy useState are present
- `build-check` — verifies Next.js builds without errors

---

## 6. Invariants (never break these)

1. **Anti-flash script is mandatory** in any Next.js app with theme switching. Without it, every page refresh produces FOUC.
2. **`html[data-theme]` must be the first selector** in every theme block. JS targets `documentElement`, not `body`.
3. **Code block colors must use CSS variables** — never hard-coded hex. Any element that must change with the theme must use `var(--*)`.
4. **Lazy `useState` for theme** — never `useState('dark') + useEffect`. The lazy initializer reads `localStorage` synchronously on first render.
5. **`body` needs explicit `background`** — it does not reliably inherit `background` from `html` via CSS custom properties in all browsers.

---

## References

- `references/light-mode-overrides.md` — full list of light mode luxury CSS overrides (header, input, sidebar, scrollbar, blockquote, math tables)
- `references/github-action-template.md` — complete `frontend-theme-ci.yml` with 5 jobs and all verification steps
