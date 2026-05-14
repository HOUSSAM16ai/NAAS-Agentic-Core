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
# 1. Anti-flash file exists
ls frontend/public/theme-init.js
# Expected: file exists

# 2. layout.jsx loads it synchronously in <head>
grep "theme-init.js" frontend/app/layout.jsx
# Expected: <script src="/theme-init.js" /> (no async)

# 3. CSS selectors
grep "html\[data-theme" frontend/app/globals.css
# Expected: ≥2 results (one for light, one for dark)

# 4. No duplicate body/html blocks (Turbopack bug)
grep -c "^body {" frontend/app/globals.css
# Expected: 1 (not 2+)

# 5. Hard-coded colors in code blocks
grep -A8 "\.markdown-content pre" frontend/app/globals.css | grep "#[0-9a-f]\{6\}"
# Expected: no output (should use var(--pre-bg))

# 6. Lazy useState
grep "useState(() =>" frontend/app/components/*.jsx
# Expected: present for theme state

# 7. Production HTML verification (most reliable)
npm run build 2>/dev/null
grep "theme-init.js" frontend/.next/server/app/index.html
# Expected: <script src="/theme-init.js"> inside <head>
```

**Healthy state:**
- `frontend/public/theme-init.js` exists and is served at `/theme-init.js`
- `layout.jsx` has `<script src="/theme-init.js">` (synchronous, no async) in `<head>`
- `html[data-theme='light']` and `html[data-theme='dark']` both exist in CSS
- `html` and `body` each have ONE CSS block containing all properties
- Code block colors use `var(--pre-bg)` / `var(--code-bg)`, not hex literals
- `useState` for theme uses a lazy initializer, not `useState('dark')`

---

## 2. Root Cause Map

| Symptom | Root Cause | Fix |
|---------|-----------|-----|
| Theme toggle has no effect | `html[data-theme]` CSS selector missing | Add `html[data-theme='light/dark']` as first selector in theme blocks |
| Flash of wrong theme on refresh | No anti-flash script in `<head>` | Create `public/theme-init.js` + `<script src="/theme-init.js">` in layout |
| Anti-flash script in `<body>` not `<head>` | Next.js 16 moves `dangerouslySetInnerHTML` from `<head>` to `<body>` | Use external file in `/public` instead |
| `body` background/color missing from compiled CSS | Turbopack drops properties when same element has multiple CSS blocks | Merge all `body` properties into one `body { }` block |
| Code blocks stay dark in light mode | Hard-coded hex colors (`#0f172a`) | Replace with `var(--pre-bg)` CSS variable |
| Brief flash before correct theme | `useState('dark')` + `useEffect` pattern | Use lazy `useState(() => localStorage...)` |
| Theme applies to some elements, not all | `body` doesn't inherit from `html` | Set `background`/`color` explicitly on `body` using CSS variables |
| Browser scrollbars ignore theme | Missing `colorScheme` | Set `document.documentElement.style.colorScheme = theme` |
| Dev server shows old CSS after file change | Turbopack cache stale | `rm -rf .next` then restart dev server |

---

## 3. The Four Fixes

### Fix 1 — Anti-flash script via `/public` file

> ⚠️ **Next.js 16 App Router critical finding (verified live 2026-05-14):**
> - `<script dangerouslySetInnerHTML>` in `<head>` JSX → Next.js 16 moves it to `<body>`. Does NOT work.
> - `next/script strategy="beforeInteractive"` → executes via `__next_s` payload after runtime. Does NOT work.
> - **Only reliable solution**: external file in `/public` + `<script src>` in `<head>`.

**Step 1** — Create `frontend/public/theme-init.js`:
```javascript
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
        if (document.body) { document.body.dataset.theme = t; o.disconnect(); }
      });
      o.observe(r, { childList: true });
    }
  } catch (e) {}
})();
```

**Step 2** — Load it synchronously in `frontend/app/layout.jsx`:
```jsx
export default function RootLayout({ children }) {
  return (
    <html lang="ar" dir="rtl" suppressHydrationWarning>
      <head>
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script src="/theme-init.js" />  {/* NO async — must be synchronous */}
      </head>
      <body suppressHydrationWarning>{children}</body>
    </html>
  );
}
```

**Why `suppressHydrationWarning`:** The script mutates `html.dataset.theme` before React hydrates. Without this prop, React throws a hydration mismatch warning.

**Verify it works** — check production HTML:
```bash
npm run build
grep "theme-init.js" .next/server/app/index.html
# Expected: <script src="/theme-init.js"> inside <head>
```

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

Also split `body, html { ... }` into separate rules. **Critical Turbopack warning:**

> ⚠️ **Turbopack CSS merging bug (verified live 2026-05-14):**
> Multiple blocks targeting the same element get merged — later properties win, earlier ones are dropped.
> `html, body { overflow-x: hidden }` + `body { background: var(--bg-color) }` = Turbopack keeps only `body { overflow-x: hidden; max-width: 100vw }` and **drops** `background` and `color`.

**WRONG — Turbopack drops background/color:**
```css
html, body { overflow-x: hidden; max-width: 100vw; }
body { background: var(--bg-color); color: var(--text-color); }  /* DROPPED */
```

**CORRECT — one block per element, all properties together:**
```css
html {
  overflow-x: hidden;
  max-width: 100vw;
  background: var(--bg-color);
  color: var(--text-color);
  transition: background-color 0.3s ease, color 0.3s ease;
}

body {
  overflow-x: hidden;
  max-width: 100vw;
  background: var(--bg-color);  /* explicit — body doesn't always inherit background */
  color: var(--text-color);
  transition: background-color 0.3s ease, color 0.3s ease;
}
```

**Verify after build:**
```bash
npm run build
python3 -c "
import re
css = open('.next/server/app/index.html').read()
# or check the compiled CSS file
print('body has background:', 'background:var(--bg-color)' in css.replace(' ',''))
"
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

1. **Anti-flash via `/public` file** — in Next.js 16 App Router, `dangerouslySetInnerHTML` in `<head>` JSX gets moved to `<body>`. Use `frontend/public/theme-init.js` + `<script src="/theme-init.js">`.
2. **`html[data-theme]` must be the first selector** in every theme block. JS targets `documentElement`, not `body`.
3. **Code block colors must use CSS variables** — never hard-coded hex. Any element that must change with the theme must use `var(--*)`.
4. **Lazy `useState` for theme** — never `useState('dark') + useEffect`. The lazy initializer reads `localStorage` synchronously on first render.
5. **`body` needs explicit `background`** — it does not reliably inherit `background` from `html` via CSS custom properties in all browsers.
6. **One CSS block per element (Turbopack)** — never split `html` or `body` properties across multiple blocks. Turbopack merges them and drops earlier properties. All `html` properties in one `html { }` block, all `body` properties in one `body { }` block.
7. **Always verify with production build** — dev server may serve cached CSS. Run `npm run build` and check `.next/server/app/index.html` for ground truth.
8. **Theme toggle button must be always visible** (ISS-067) — never hide the theme toggle inside a dropdown menu. Place a dedicated button (`header-theme-btn`) directly in the header, outside any conditional render block.
9. **`:root` must contain ALL CSS variables** (ISS-067) — even if `html[data-theme]` blocks define them, `:root` must have safe fallback values for every variable. Missing `:root` fallbacks cause `undefined` variables before theme is applied.

---

## 7. CI Gate: theme-button-gate (ISS-067)

The `theme-button-gate` job in `frontend-theme-ci.yml` enforces invariants 8 and 9:

```yaml
- name: Verify theme button is outside dropdown
  shell: bash
  run: |
    theme_line=$(grep -n "header-theme-btn" frontend/app/components/CogniForgeApp.jsx \
      | head -1 | cut -d: -f1)
    menu_line=$(grep -n "isMenuOpen &&" frontend/app/components/CogniForgeApp.jsx \
      | head -1 | cut -d: -f1)
    if [ "$theme_line" -ge "$menu_line" ]; then
      echo "❌ Theme button must appear BEFORE dropdown"
      exit 1
    fi
```

This prevents regression where the button gets moved back inside the dropdown.

---

## References

- `references/light-mode-overrides.md` — full list of light mode luxury CSS overrides (header, input, sidebar, scrollbar, blockquote, math tables)
- `references/github-action-template.md` — complete `frontend-theme-ci.yml` with 6 jobs and all verification steps (updated for ISS-067: theme-button-gate + `:root` fallback check)
