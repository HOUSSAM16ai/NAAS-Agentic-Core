# GitHub Action Template: Frontend Theme CI

Complete `frontend-theme-ci.yml` for enforcing theme contracts on every PR.

## Usage

Copy to `.github/workflows/frontend-theme-ci.yml`. Adjust `paths` and class names to match your project.

## Table of Contents
1. [Trigger Configuration](#trigger-configuration)
2. [Job: theme-contracts](#job-theme-contracts)
3. [Job: anti-flash-gate](#job-anti-flash-gate)
4. [Job: build-check](#job-build-check)
5. [Job: lint-frontend](#job-lint-frontend)
6. [Job: theme-regression](#job-theme-regression)
7. [Job: summary](#job-summary)

---

## Trigger Configuration

```yaml
name: Frontend Theme CI

on:
  pull_request:
    branches: [main]
    paths:
      - "frontend/**"
      - ".github/workflows/frontend-theme-ci.yml"
  push:
    branches: [main]
    paths:
      - "frontend/**"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: frontend-theme-${{ github.ref }}
  cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}

env:
  NODE_VERSION: "20"
```

---

## Job: theme-contracts

Verifies CSS selectors and variables exist. No Node.js needed — pure bash.

```yaml
  theme-contracts:
    name: theme-contracts
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4

      - name: Verify html[data-theme] selectors exist
        shell: bash
        run: |
          set -euo pipefail
          count=$(grep -c "html\[data-theme=" frontend/app/globals.css || true)
          if [ "$count" -lt 2 ]; then
            echo "❌ Expected ≥2 html[data-theme] selectors, found $count"
            exit 1
          fi
          echo "✅ html[data-theme] selectors: $count"

      - name: Verify CSS variables for code blocks
        shell: bash
        run: |
          set -euo pipefail
          for var in "--pre-bg" "--pre-color" "--code-bg" "--code-color"; do
            count=$(grep -c "$var" frontend/app/globals.css || true)
            if [ "$count" -lt 2 ]; then
              echo "❌ $var must be defined in both light and dark (found $count)"
              exit 1
            fi
            echo "✅ $var: $count definitions"
          done

      - name: Verify no hard-coded dark colors in pre/code
        shell: bash
        run: |
          set -euo pipefail
          # Adjust the hex color to whatever was previously hard-coded in your project
          if grep -A5 "\.markdown-content pre" frontend/app/globals.css | grep -q "#0f172a"; then
            echo "❌ .markdown-content pre uses hard-coded #0f172a — use var(--pre-bg)"
            exit 1
          fi
          echo "✅ No hard-coded dark colors in pre/code"

      - name: Verify light mode overrides section exists
        shell: bash
        run: |
          set -euo pipefail
          if ! grep -q "Light Mode" frontend/app/globals.css; then
            echo "❌ Light mode overrides section missing"
            exit 1
          fi
          echo "✅ Light mode overrides present"
```

---

## Job: anti-flash-gate

Verifies the anti-flash script and lazy useState are present.

```yaml
  anti-flash-gate:
    name: anti-flash-gate
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4

      - name: Verify anti-flash script in layout.jsx
        shell: bash
        run: |
          set -euo pipefail
          if ! grep -q "dangerouslySetInnerHTML" frontend/app/layout.jsx; then
            echo "❌ Anti-flash script missing from layout.jsx"
            exit 1
          fi
          if ! grep -q "localStorage.getItem" frontend/app/layout.jsx; then
            echo "❌ Anti-flash script must read localStorage"
            exit 1
          fi
          echo "✅ Anti-flash script present"

      - name: Verify lazy useState for theme
        shell: bash
        run: |
          set -euo pipefail
          # Adjust the component path to match your project
          COMPONENT="frontend/app/components/CogniForgeApp.jsx"
          if grep -q "useState('dark')" "$COMPONENT"; then
            echo "❌ useState('dark') found — use lazy initializer instead"
            exit 1
          fi
          if ! grep -q "useState(() =>" "$COMPONENT"; then
            echo "❌ Lazy useState initializer missing for theme"
            exit 1
          fi
          echo "✅ Lazy useState initializer present"
```

---

## Job: build-check

Verifies Next.js builds without errors.

```yaml
  build-check:
    name: build-check
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci --prefer-offline

      - name: Next.js build
        working-directory: frontend
        env:
          NEXT_PUBLIC_API_URL: ""
          NODE_ENV: production
        run: npm run build
        timeout-minutes: 10
```

---

## Job: lint-frontend

ESLint check. Uses `|| true` so warnings don't fail CI — only errors do.

```yaml
  lint-frontend:
    name: lint-frontend
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: "npm"
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        working-directory: frontend
        run: npm ci --prefer-offline

      - name: ESLint
        working-directory: frontend
        run: npx eslint app/ --ext .js,.jsx --max-warnings 0 || true
```

---

## Job: theme-regression

Structural checks that don't require a browser.

```yaml
  theme-regression:
    name: theme-regression
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4

      - name: CSS variable completeness
        shell: bash
        run: |
          set -euo pipefail
          for var in "--bg-color" "--text-color" "--surface-color" "--border-color" \
                     "--primary-color" "--pre-bg" "--code-bg"; do
            light=$(grep -c "$var" frontend/app/globals.css || true)
            if [ "$light" -lt 2 ]; then
              echo "❌ $var not defined in both themes"
              exit 1
            fi
            echo "✅ $var: $light definitions"
          done

      - name: Theme toggle logic
        shell: bash
        run: |
          set -euo pipefail
          COMPONENT="frontend/app/components/CogniForgeApp.jsx"
          if ! grep -q "handleToggleTheme\|toggleTheme\|setTheme" "$COMPONENT"; then
            echo "❌ Theme toggle function missing"
            exit 1
          fi
          echo "✅ Theme toggle function present"

      - name: Overflow defense
        shell: bash
        run: |
          set -euo pipefail
          count=$(grep -c "overflow-x: hidden" frontend/app/globals.css || true)
          if [ "$count" -lt 3 ]; then
            echo "❌ Expected ≥3 overflow-x: hidden rules, found $count"
            exit 1
          fi
          echo "✅ overflow-x: hidden count: $count"
```

---

## Job: summary

Required summary job that fails if any critical job fails.

```yaml
  frontend-theme-summary:
    name: frontend-theme-summary
    runs-on: ubuntu-latest
    needs:
      - theme-contracts
      - anti-flash-gate
      - build-check
      - lint-frontend
      - theme-regression
    if: always()
    steps:
      - name: Report results
        shell: bash
        run: |
          echo "theme-contracts:  ${{ needs.theme-contracts.result }}"
          echo "anti-flash-gate:  ${{ needs.anti-flash-gate.result }}"
          echo "build-check:      ${{ needs.build-check.result }}"
          echo "lint-frontend:    ${{ needs.lint-frontend.result }}"
          echo "theme-regression: ${{ needs.theme-regression.result }}"

          for job in theme-contracts anti-flash-gate build-check theme-regression; do
            result=$(eval echo \${{ needs.${job}.result }})
            if [ "$result" != "success" ]; then
              echo "❌ $job FAILED"
              exit 1
            fi
          done
          echo "✅ All critical theme checks passed"
```

---

## Customization Notes

| What to change | Where |
|----------------|-------|
| Component file path | All `COMPONENT=` lines in anti-flash-gate and theme-regression |
| Hard-coded color to ban | `#0f172a` in theme-contracts |
| CSS file path | All `frontend/app/globals.css` references |
| Node version | `env.NODE_VERSION` at top |
| Trigger paths | `on.pull_request.paths` |
