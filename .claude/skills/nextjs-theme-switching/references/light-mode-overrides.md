# Light Mode Luxury CSS Overrides

Complete list of `html[data-theme='light']` scoped overrides for a premium light mode experience. Add these at the end of `globals.css` after all base styles.

## Table of Contents
1. [Header](#header)
2. [Header Menu](#header-menu)
3. [Input Area](#input-area)
4. [User Message Bubble](#user-message-bubble)
5. [Sidebar](#sidebar)
6. [Login / Register Forms](#login--register-forms)
7. [Conversation Items](#conversation-items)
8. [Mission Buttons](#mission-buttons)
9. [Agent Sidebar](#agent-sidebar)
10. [Blockquote](#blockquote)
11. [Math Tables](#math-tables)
12. [Scrollbar](#scrollbar)
13. [Theme Toggle Button](#theme-toggle-button)
14. [Exam Badge](#exam-badge)

---

## Header

```css
html[data-theme='light'] .header,
body[data-theme='light'] .header {
    border-bottom: 1px solid var(--border-color);
    box-shadow: 0 1px 3px rgb(0 0 0 / 0.04);
}
```

## Header Menu

```css
html[data-theme='light'] .header-menu,
body[data-theme='light'] .header-menu {
    box-shadow: 0 4px 16px rgb(0 0 0 / 0.10), 0 1px 4px rgb(0 0 0 / 0.06);
}

html[data-theme='light'] .header-menu-item:hover,
body[data-theme='light'] .header-menu-item:hover {
    background-color: var(--surface-elevated);
}
```

## Input Area

```css
html[data-theme='light'] .input-area,
body[data-theme='light'] .input-area {
    border: 1.5px solid var(--border-color);
    box-shadow: 0 2px 8px rgb(0 0 0 / 0.05);
}

html[data-theme='light'] .input-area:focus-within,
body[data-theme='light'] .input-area:focus-within {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.10), 0 2px 8px rgb(0 0 0 / 0.05);
}
```

## User Message Bubble

```css
html[data-theme='light'] .message.user .message-bubble,
body[data-theme='light'] .message.user .message-bubble {
    box-shadow: 0 2px 8px rgb(37 99 235 / 0.18);
}
```

## Sidebar

```css
html[data-theme='light'] .sidebar,
body[data-theme='light'] .sidebar {
    border-left: 1px solid var(--border-color);
    box-shadow: -4px 0 16px rgb(0 0 0 / 0.06);
}
```

## Login / Register Forms

```css
html[data-theme='light'] .login-form,
html[data-theme='light'] .register-form,
body[data-theme='light'] .login-form,
body[data-theme='light'] .register-form {
    box-shadow: 0 8px 32px rgb(0 0 0 / 0.10), 0 2px 8px rgb(0 0 0 / 0.06);
}
```

## Conversation Items

```css
html[data-theme='light'] .conversation-item:hover,
body[data-theme='light'] .conversation-item:hover {
    background-color: var(--surface-elevated);
}
```

## Mission Buttons

```css
html[data-theme='light'] .mission-btn,
body[data-theme='light'] .mission-btn {
    box-shadow: 0 2px 8px rgb(0 0 0 / 0.06);
}

html[data-theme='light'] .mission-btn:hover,
body[data-theme='light'] .mission-btn:hover {
    box-shadow: 0 4px 16px rgb(0 0 0 / 0.10);
}
```

## Agent Sidebar

```css
html[data-theme='light'] .agent-sidebar,
body[data-theme='light'] .agent-sidebar {
    border-right: 1px solid var(--border-color);
    box-shadow: 4px 0 16px rgb(0 0 0 / 0.06);
}
```

## Blockquote

```css
html[data-theme='light'] .md-blockquote,
body[data-theme='light'] .md-blockquote {
    background: rgba(37, 99, 235, 0.04);
    border-right: 3px solid var(--primary-color);
    color: var(--text-secondary);
}
```

## Math Tables

```css
html[data-theme='light'] .math-table th,
body[data-theme='light'] .math-table th {
    background: rgba(37, 99, 235, 0.06);
}
```

## Scrollbar

```css
html[data-theme='light'] ::-webkit-scrollbar-track,
body[data-theme='light'] ::-webkit-scrollbar-track {
    background: var(--surface-elevated);
}

html[data-theme='light'] ::-webkit-scrollbar-thumb,
body[data-theme='light'] ::-webkit-scrollbar-thumb {
    background: #d4d4d8;
    border-radius: 4px;
}

html[data-theme='light'] ::-webkit-scrollbar-thumb:hover,
body[data-theme='light'] ::-webkit-scrollbar-thumb:hover {
    background: #a1a1aa;
}
```

## Theme Toggle Button

```css
html[data-theme='light'] .header-menu-btn,
body[data-theme='light'] .header-menu-btn {
    color: var(--text-color);
}

html[data-theme='light'] .header-menu-btn:hover,
body[data-theme='light'] .header-menu-btn:hover {
    background-color: var(--surface-elevated);
}
```

## Exam Badge

```css
html[data-theme='light'] .exam-badge,
body[data-theme='light'] .exam-badge {
    background: rgba(37, 99, 235, 0.08);
    color: var(--primary-color);
    border: 1px solid rgba(37, 99, 235, 0.15);
}
```

---

## Design Principles for Light Mode

- **Shadows replace borders**: In dark mode, borders define separation. In light mode, subtle shadows (`rgb(0 0 0 / 0.04–0.10)`) feel more premium.
- **Blue accent for focus**: Use `rgba(37, 99, 235, 0.10)` for focus rings — visible but not aggressive.
- **Surface elevation**: `--surface-elevated` (`#fafafa`) for hover states instead of a flat color change.
- **No hard shadows**: Max shadow opacity `0.10` for most elements, `0.18` only for primary-colored elements (user bubbles).
