# `docs/evidence/`

Visual evidence attached to pull requests, committed so a reviewer can see it
from the diff and so the link in a PR body does not rot.

D-270 L1 asks for the command and its output; `validate_pr_description.py`
additionally requires a screenshot on any change that touches `frontend/`,
because what a student sees should be visible in review. Files here are that
screenshot — captured from a real run, never a mock-up, and named for the change
they belong to.

| file | what it shows |
|---|---|
| `react19-frontend-2026-08-24.png` | the login screen served by `next start` after the React 18.3.1 → 19.2.8 / Next 16.3.0 → 16.3.1 / katex 0.16 → 0.18 uplift (#2291, #2292): Arabic RTL layout, theme tokens and form controls all intact. |
