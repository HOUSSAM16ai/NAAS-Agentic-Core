#!/usr/bin/env bash
###############################################################################
# supervisor.sh - Application Lifecycle Supervisor (v2.1)
#
# المشرف على دورة حياة التطبيق
# Application Lifecycle Supervisor
#
# المسؤوليات (Responsibilities):
#   1. تثبيت التبعيات (Dependencies Installation)
#   2. تشغيل الترحيلات (Database Migrations)
#   3. إنشاء المستخدم الإداري (Admin Seeding)
#   4. إطلاق خادم التطبيق (Application Server)
#   5. فحص الصحة (Health Monitoring)
#
# المبادئ (Principles):
#   - Sequential Execution: Each step waits for previous
#   - Idempotent Operations: Safe to run multiple times
#   - Health-Gated: Don't signal ready until healthy
#   - Comprehensive Logging: Every action is logged
#
# الإصدار (Version): 2.1.0
# التاريخ (Date): 2026-01-18
###############################################################################

set -Eeuo pipefail

# ==============================================================================
# INITIALIZATION (التهيئة)
# ==============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly APP_ROOT="/app"
readonly APP_PORT="${PORT:-8000}"
readonly FRONTEND_PORT="${FRONTEND_PORT:-5000}"
readonly HEALTH_ENDPOINT="http://localhost:${APP_PORT}/health"

cd "$APP_ROOT"

if [ -f "frontend/package.json" ]; then
    export ENABLE_STATIC_FILES="${ENABLE_STATIC_FILES:-0}"
else
    export ENABLE_STATIC_FILES="${ENABLE_STATIC_FILES:-1}"
fi

# Load core library
if [ -f "$SCRIPT_DIR/lib/lifecycle_core.sh" ]; then
    source "$SCRIPT_DIR/lib/lifecycle_core.sh"
else
    echo "ERROR: lifecycle_core.sh not found" >&2
    exit 1
fi

# Error trap
trap 'lifecycle_error "Supervisor failed at line $LINENO"' ERR

lifecycle_info "═══════════════════════════════════════════════════════"
lifecycle_info "🎯 Application Lifecycle Supervisor Started"
lifecycle_info "   Version: 2.1.0 (Async Frontend)"
lifecycle_info "   PID: $$"
lifecycle_info "   Timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
lifecycle_info "═══════════════════════════════════════════════════════"

# ==============================================================================
# STEP 0: System Readiness & Environment (جاهزية النظام والبيئة)
# ==============================================================================

lifecycle_info "Step 0/5: System readiness check..."

# Give container time to fully initialize
# CODESPACES: Longer stabilization time for cloud environments
if [ -n "${CODESPACES:-}" ]; then
    lifecycle_info "Detected Codespaces environment - using extended stabilization (5s)..."
    sleep 5
else
    lifecycle_info "Waiting for system stabilization (2s)..."
    sleep 2
fi

# ── ENV INJECTION ─────────────────────────────────────────────────────────────
# Priority order (highest → lowest):
#   1. Process environment (injected by devcontainer.json remoteEnv / Gitpod secrets)
#   2. .devcontainer/secrets.env  ← local fallback, git-ignored, never committed
#   3. Existing .env file values (preserved if already set)
#   4. Safe development defaults (sqlite only in TESTING=1 mode)
#
# CRITICAL: DATABASE_URL=sqlite in ENVIRONMENT=development causes AppSettings to
# raise a ValidationError and crash uvicorn on import. We must inject the real
# DATABASE_URL from the process environment before uvicorn starts.
#
# HOW TO USE secrets.env (Codespaces without Secrets configured):
#   cp .devcontainer/secrets.env.example .devcontainer/secrets.env
#   # fill in real values — this file is git-ignored
# ──────────────────────────────────────────────────────────────────────────────

_inject_env_secrets() {
    local env_file=".env"
    local changed=0

    # ── Load Gitpod file secrets (injected as files under /usr/local/secrets/) ──
    # Gitpod Flex injects secrets as files when secretType=file in the environment
    # spec. These are NOT available as env vars — must be read explicitly.
    local gitpod_secrets_dir="/usr/local/secrets"
    if [ -d "$gitpod_secrets_dir" ]; then
        for secret_file in "$gitpod_secrets_dir"/*; do
            [ -f "$secret_file" ] || continue
            local secret_name
            secret_name="$(basename "$secret_file")"
            local secret_val
            secret_val="$(tr -d '\n\r ' < "$secret_file")"
            if [ -n "$secret_val" ] && [ -z "${!secret_name:-}" ]; then
                export "$secret_name=$secret_val"
                lifecycle_info "  /usr/local/secrets/$secret_name -> injected"
            fi
        done
    fi

    # ── Load .devcontainer/secrets.env as fallback when Codespaces Secrets absent ──
    # This file is git-ignored. It lets developers run without configuring
    # Codespaces Secrets — just copy secrets.env.example and fill in values.
    #
    # D-WS-004 fix: devcontainer.json injects empty strings for unset secrets
    # (e.g. APP_DATABASE_URL=""). The old check `[ -z "${!key:-}" ]` treated
    # empty-string as "not set" and correctly injected — but only when the
    # variable was truly absent. When devcontainer sets it to "", the variable
    # IS set (just empty), so we must check for empty OR unset explicitly.
    local secrets_file="$SCRIPT_DIR/secrets.env"
    if [ -f "$secrets_file" ]; then
        lifecycle_info "Loading fallback secrets from .devcontainer/secrets.env..."
        while IFS= read -r line; do
            # تجاهل التعليقات والأسطر الفارغة
            [[ "$line" =~ ^[[:space:]]*# ]] && continue
            [[ -z "${line// }" ]] && continue
            # استخراج المفتاح والقيمة — نقطع عند أول = فقط
            local key="${line%%=*}"
            local val="${line#*=}"
            [[ -z "$key" ]] && continue
            # D-WS-004: inject when unset OR empty (devcontainer sets empty strings
            # for secrets not configured in Gitpod/Codespaces environment)
            local current_val="${!key:-}"
            if [ -z "$current_val" ]; then
                export "$key=$val"
                lifecycle_info "  secrets.env -> $key injected"
            fi
        done < "$secrets_file"
    fi

    # Resolve the real DATABASE_URL: prefer APP_DATABASE_URL, then DATABASE_URL
    local real_db_url="${APP_DATABASE_URL:-${DATABASE_URL:-}}"

    # If .env doesn't exist, create it with safe defaults
    if [ ! -f "$env_file" ]; then
        lifecycle_info "Creating .env file..."
        cat > "$env_file" <<'ENVEOF'
# Auto-generated by supervisor.sh — overwritten by env injection below
ENVIRONMENT=development
SECRET_KEY=dev-secret-change-me
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=password
ADMIN_NAME=AdminUser
ENVEOF
        changed=1
    fi

    # Helper: set or replace a key in .env
    _set_env_key() {
        local key="$1" val="$2"
        if grep -q "^${key}=" "$env_file" 2>/dev/null; then
            # Replace existing line (portable sed)
            sed -i "s|^${key}=.*|${key}=${val}|" "$env_file"
        else
            echo "${key}=${val}" >> "$env_file"
        fi
    }

    # ── DATABASE_URL ──────────────────────────────────────────────────────────
    if [ -n "$real_db_url" ]; then
        lifecycle_info "Injecting DATABASE_URL from process environment..."
        _set_env_key "DATABASE_URL" "$real_db_url"
        _set_env_key "APP_DATABASE_URL" "$real_db_url"
        changed=1
    else
        # No real DB URL available — check if .env already has a non-sqlite one
        local existing_db
        existing_db=$(grep "^DATABASE_URL=" "$env_file" 2>/dev/null | cut -d= -f2- || true)
        if [ -z "$existing_db" ] || echo "$existing_db" | grep -q "sqlite"; then
            # ─────────────────────────────────────────────────────────────────
            # ISS-094 round 2 (D-095 — 2026-05-28): NEVER auto-set ENVIRONMENT=testing.
            #
            # السبب الجذري لـ "kick-to-login" المستمر بعد ISS-092/ISS-093/ISS-094:
            #   1. secrets.env مفقود أو Codespaces Secrets غير مُهيَّأة
            #   2. real_db_url فارغ → supervisor يضبط ENVIRONMENT=testing
            #   3. crypto.py يقرأ ENVIRONMENT=testing → ACCESS_EXPIRE_MINUTES=30
            #   4. بعد 30 دقيقة من الجلسة، كل token ينتهي → 4401 → kick
            #
            # الحل: حتى لو وقعنا في SQLite mode (degraded LLM)، نُبقي
            # ENVIRONMENT=development لضمان tokens لـ 480 دقيقة.
            # TESTING=1 يبقى كإشارة منفصلة للـ code paths التي تحتاجها.
            # ─────────────────────────────────────────────────────────────────
            lifecycle_error "═══════════════════════════════════════════════════════════════"
            lifecycle_error "🚨 CRITICAL: DATABASE_URL not configured — DEGRADED MODE"
            lifecycle_error "   Falling back to in-memory SQLite (data will be LOST on restart)"
            lifecycle_error ""
            lifecycle_error "   To fix permanently, do ONE of the following:"
            lifecycle_error "   1. Configure Codespaces Secrets at:"
            lifecycle_error "      https://github.com/settings/codespaces"
            lifecycle_error "      Add: APP_DATABASE_URL, OPENROUTER_API_KEY"
            lifecycle_error ""
            lifecycle_error "   2. Or create .devcontainer/secrets.env:"
            lifecycle_error "      cp .devcontainer/secrets.env.example .devcontainer/secrets.env"
            lifecycle_error "      # then edit and fill in real values"
            lifecycle_error "═══════════════════════════════════════════════════════════════"
            _set_env_key "DATABASE_URL" "sqlite+aiosqlite:///:memory:"
            # D-095: do NOT set ENVIRONMENT=testing here — keeps JWT lifetime at 480 min
            #        (development mode). Otherwise users get kicked to login after 30 min.
            _set_env_key "ENVIRONMENT" "development"
            # TESTING=1 is a separate flag for code paths that need it (LLM mocking, etc.)
            _set_env_key "TESTING" "1"
            changed=1
        fi
    fi

    # ── ENVIRONMENT (D-ISS-092 — 2026-05-28): ضمان development عند وجود DB حقيقي ──
    # إذا كان DATABASE_URL حقيقياً (ليس sqlite)، يجب أن يكون ENVIRONMENT=development
    # لضمان token lifetime = 480 دقيقة (8 ساعات) بدلاً من 30 دقيقة.
    if [ -n "$real_db_url" ] && ! echo "$real_db_url" | grep -q "sqlite"; then
        _set_env_key "ENVIRONMENT" "development"
        _set_env_key "TESTING" ""
        changed=1
    fi

    # ── OPENROUTER_API_KEY ────────────────────────────────────────────────────
    if [ -n "${OPENROUTER_API_KEY:-}" ]; then
        _set_env_key "OPENROUTER_API_KEY" "$OPENROUTER_API_KEY"
        changed=1
    fi

    # ── SECRET_KEY ────────────────────────────────────────────────────────────
    if [ -n "${SECRET_KEY:-}" ]; then
        _set_env_key "SECRET_KEY" "$SECRET_KEY"
        changed=1
    fi

    # ── TAVILY_API_KEY ────────────────────────────────────────────────────────
    if [ -n "${TAVILY_API_KEY:-}" ]; then
        _set_env_key "TAVILY_API_KEY" "$TAVILY_API_KEY"
        changed=1
    fi

    # ── OPENAI_API_KEY ────────────────────────────────────────────────────────
    if [ -n "${OPENAI_API_KEY:-}" ]; then
        _set_env_key "OPENAI_API_KEY" "$OPENAI_API_KEY"
        changed=1
    fi

    # ── BACKEND_CORS_ORIGINS (D-WS-002 + D-WS-GITPOD-001) ───────────────────
    # يُعيَّن دائماً لضمان تحديث القيمة عند إضافة نطاقات جديدة.
    # D-WS-GITPOD-001: يشمل *.gitpod.dev (Gitpod Flex/Ona) و *.app.github.dev (Codespaces).
    # ملاحظة: FastAPI CORSMiddleware يقبل wildcards فقط في subdomains (*.example.com).
    _set_env_key "BACKEND_CORS_ORIGINS" "http://localhost:3000,http://localhost:5000,http://127.0.0.1:3000,http://127.0.0.1:5000,https://*.gitpod.io,https://*.gitpod.dev,https://*.eu-central-1-01.gitpod.dev,https://*.eu-central-1-02.gitpod.dev,https://*.us-east-1-01.gitpod.dev,https://*.app.github.dev,https://*.preview.app.github.dev,https://*.replit.dev,https://*.replit.app"
    changed=1

    # ── ALLOWED_HOSTS (D-WS-002 + D-WS-GITPOD-001) ──────────────────────────
    # يضمن أن TrustedHostMiddleware يقبل Gitpod/Ona/Codespaces hosts.
    # D-WS-GITPOD-001: Gitpod Flex/Ona يستخدم *.gitpod.dev (ليس *.gitpod.io فقط)
    # مثال: 8000--019e6245-....eu-central-1-01.gitpod.dev
    # يُعيَّن دائماً لضمان تحديث القيمة عند إضافة نطاقات جديدة.
    _set_env_key "ALLOWED_HOSTS" "localhost,127.0.0.1,testserver,test,*.gitpod.io,*.ws-eu.gitpod.io,*.ws-us.gitpod.io,*.gitpod.dev,*.eu-central-1-01.gitpod.dev,*.eu-central-1-02.gitpod.dev,*.us-east-1-01.gitpod.dev,*.app.github.dev,*.preview.app.github.dev,*.replit.dev,*.replit.app,*.janeway.replit.dev"
    changed=1

    if [ "$changed" -eq 1 ]; then
        lifecycle_info "✅ .env updated with injected secrets"
    else
        lifecycle_info "✅ .env already configured (no changes needed)"
    fi
}

_inject_env_secrets

# ── D-SECRET-001: ضمان SECRET_KEY ثابت عبر كل restarts ──────────────────────
# إذا كان SECRET_KEY لا يزال القيمة الافتراضية الضعيفة بعد _inject_env_secrets،
# نقرأه من ملف state الثابت (يُنشئه _get_or_create_dev_secret_key في Python).
# هذا يضمن أن كل الخدمات تستخدم نفس المفتاح حتى بدون Gitpod Secrets.
_ensure_stable_secret_key() {
    local state_key_file="$APP_ROOT/.devcontainer/state/dev_secret_key"
    local current_key="${SECRET_KEY:-}"

    # D-ISS-092 (2026-05-28): الأولوية للملف على القرص دائماً.
    # السبب: إذا تغيّر SECRET_KEY بين restarts (من .env أو Codespaces Secrets)،
    # كل الـ tokens القديمة تُبطَل → 4401 → kick-to-login loop.
    # الملف على القرص يضمن نفس المفتاح عبر كل restarts في نفس الـ Codespace.
    #
    # الاستثناء الوحيد: إذا كان الملف غير موجود أو فارغ → استخدم current_key إذا كان قوياً.

    # 1. إذا كان الملف موجوداً ومفتاحه قوي → استخدمه دائماً (حتى لو current_key مختلف)
    if [ -f "$state_key_file" ]; then
        local stored_key
        stored_key=$(cat "$state_key_file" 2>/dev/null | tr -d '[:space:]')
        if [ -n "$stored_key" ] && [ "${#stored_key}" -ge 32 ]; then
            export SECRET_KEY="$stored_key"
            lifecycle_info "SECRET_KEY: loaded from state file (${#stored_key} chars) — disk wins"
            return 0
        fi
    fi

    # 2. الملف غير موجود أو فارغ — إذا كان current_key قوياً → احفظه واستخدمه
    if [ -n "$current_key" ] && [ "${#current_key}" -ge 32 ] \
       && [ "$current_key" != "dev-secret-change-me" ] \
       && [ "$current_key" != "changeme" ]; then
        mkdir -p "$(dirname "$state_key_file")"
        echo "$current_key" > "$state_key_file"
        lifecycle_info "SECRET_KEY: strong key saved to state (${#current_key} chars)"
        return 0
    fi

    # 3. لا ملف ولا مفتاح قوي → أنشئ مفتاحاً جديداً ثابتاً واحفظه
    local new_key
    new_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))" 2>/dev/null \
              || openssl rand -base64 48 2>/dev/null \
              || echo "cogniforge_fallback_$(date +%s)_key_for_dev_only")
    mkdir -p "$(dirname "$state_key_file")"
    echo "$new_key" > "$state_key_file"
    export SECRET_KEY="$new_key"
    lifecycle_info "SECRET_KEY: generated new stable key (${#new_key} chars) — saved to state"
}
_ensure_stable_secret_key

# D-ISS-092: بعد _ensure_stable_secret_key، اكتب SECRET_KEY النهائي في .env
# لضمان أن uvicorn يقرأ نفس المفتاح الذي يستخدمه الـ state file.
# ملاحظة: _set_env_key تستخدم env_file المحلي لـ _inject_env_secrets — نكتب مباشرة هنا.
# لا نستخدم local هنا (خارج دالة) — نستخدم متغير عادي ثم نحذفه.
if [ -n "${SECRET_KEY:-}" ]; then
    _iss092_env_f=".env"
    if grep -q "^SECRET_KEY=" "$_iss092_env_f" 2>/dev/null; then
        sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" "$_iss092_env_f"
    else
        echo "SECRET_KEY=${SECRET_KEY}" >> "$_iss092_env_f"
    fi
    unset _iss092_env_f
    lifecycle_info "SECRET_KEY written to .env (${#SECRET_KEY} chars)"
fi

lifecycle_info "✅ System ready"
lifecycle_set_state "system_ready" "$(date +%s)"

# ==============================================================================
# STEP 1: Dependencies Installation (تثبيت التبعيات)
# ==============================================================================

lifecycle_info "Step 1/5: Dependencies installation..."

install_dependencies() {
    lifecycle_info "Installing Python dependencies..."
    
    if [ ! -f "requirements.txt" ]; then
        lifecycle_error "requirements.txt not found"
        return 1
    fi
    
    # OPTIMIZATION: Install CPU-only torch first if not present
    # This prevents runtime installation from downloading 2GB+ CUDA wheels if image wasn't rebuilt
    if ! python -c "import torch" 2>/dev/null; then
        lifecycle_info "Installing CPU-only Torch (optimization)..."
        pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu || true
    fi

    # Use pip with caching for faster subsequent runs
    if pip install -r requirements.txt -c constraints.txt; then
        lifecycle_info "✅ Dependencies installed successfully"
        return 0
    else
        lifecycle_error "Failed to install dependencies"
        return 1
    fi
}

# Run once per container lifecycle
if ! lifecycle_has_state "dependencies_installed"; then
    if install_dependencies; then
        lifecycle_set_state "dependencies_installed" "$(date +%s)"
    else
        lifecycle_error "Dependency installation failed"
        exit 1
    fi
else
    lifecycle_info "Dependencies already installed (skipping)"
fi

# ==============================================================================
# STEP 2: Database Migrations (ترحيلات قاعدة البيانات)
# ==============================================================================

lifecycle_info "Step 2/5: Database migrations..."

run_migrations() {
    lifecycle_info "Running database migrations..."
    
    if [ -f "scripts/smart_migrate.py" ]; then
        # IMPORTANT: Must pass 'upgrade head' to smart_migrate.py
        if python scripts/smart_migrate.py upgrade head; then
            lifecycle_info "✅ Migrations completed successfully"
            return 0
        else
            lifecycle_warn "Migration script failed (non-fatal)"
            return 0  # Don't fail supervisor on migration errors
        fi
    else
        lifecycle_warn "Migration script not found (skipping)"
        return 0
    fi
}

if run_migrations; then
    lifecycle_set_state "migrations_completed" "$(date +%s)"
else
    lifecycle_warn "Migrations had issues but continuing..."
fi

# ==============================================================================
# STEP 3: Admin User Seeding (إنشاء المستخدم الإداري)
# ==============================================================================

lifecycle_info "Step 3/5: Admin user seeding..."

seed_admin() {
    lifecycle_info "Seeding admin user..."
    
    # Check for ensure_admin.py (Correct script name)
    if [ -f "scripts/ensure_admin.py" ]; then
        if python scripts/ensure_admin.py; then
            lifecycle_info "✅ Admin user seeded successfully"
            return 0
        else
            lifecycle_warn "Admin seeding failed (non-fatal)"
            return 0  # Don't fail supervisor on seeding errors
        fi
    else
        lifecycle_warn "Admin seeding script (scripts/ensure_admin.py) not found (skipping)"
        return 0
    fi
}

if seed_admin; then
    lifecycle_set_state "admin_seeded" "$(date +%s)"
else
    lifecycle_warn "Admin seeding had issues but continuing..."
fi

# ==============================================================================
# STEP 4: Application Server Launch (إطلاق خادم التطبيق)
# ==============================================================================

lifecycle_info "Step 4/5: Application server launch..."

# ── Export secrets from .env into the current shell before launching uvicorn ──
# This is required because app/core/settings/base.py reads DATABASE_URL and
# APP_DATABASE_URL via os.environ at module-import time (before pydantic-settings
# reads the .env file). Without this export, uvicorn's worker crashes on import
# with "DATABASE_URL is missing" even when .env is correctly populated.
_export_env_file() {
    local env_file=".env"
    if [ ! -f "$env_file" ]; then
        lifecycle_warn "No .env file found — uvicorn will rely on process environment only"
        return 0
    fi
    local exported=0
    while IFS= read -r line || [ -n "$line" ]; do
        # Skip comments and blank lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// }" ]] && continue
        # Only export KEY=VALUE lines
        if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
            local key="${BASH_REMATCH[1]}"
            local val="${BASH_REMATCH[2]}"
            # D-WS-004: inject when unset OR empty.
            # devcontainer.json sets empty strings for unconfigured secrets,
            # so we must treat "" the same as "unset" here.
            local current_val="${!key:-}"
            if [ -z "$current_val" ]; then
                export "$key"="$val"
                exported=$((exported + 1))
            fi
        fi
    done < "$env_file"
    lifecycle_info "Exported $exported secrets from .env into process environment"
}
_export_env_file

# Acquire lock to prevent multiple instances
if ! lifecycle_acquire_lock "uvicorn_launch" 60; then
    lifecycle_error "Failed to acquire launch lock (another instance running?)"
    exit 1
fi

# Check if already running AND actually listening (not just a zombie process)
# D-SQLITE-GUARD: also verify the running process is NOT using SQLite.
# If DATABASE_URL=sqlite in the process env, the backend is in degraded mode
# and must be restarted with the real Supabase URL from secrets.env.
_uvicorn_healthy() {
    local pid
    pid=$(lifecycle_get_state "uvicorn_pid" 2>/dev/null || true)
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    curl -sf --connect-timeout 2 "$HEALTH_ENDPOINT" >/dev/null 2>&1 || return 1
    # Guard: reject if running with SQLite (degraded mode from a secrets-less boot)
    local proc_db
    proc_db=$(cat /proc/"$pid"/environ 2>/dev/null | tr '\0' '\n' | grep "^DATABASE_URL=" | cut -d= -f2- || true)
    if echo "$proc_db" | grep -q "sqlite"; then
        lifecycle_warn "D-SQLITE-GUARD: uvicorn PID $pid is running with SQLite — forcing restart with real DB"
        return 1
    fi
    return 0
}

if _uvicorn_healthy; then
    lifecycle_info "Application server already running and healthy"
    lifecycle_release_lock "uvicorn_launch"
else
    # Kill any stale uvicorn process that is alive but not serving
    stale_pid=$(lifecycle_get_state "uvicorn_pid" 2>/dev/null || true)
    if [ -n "$stale_pid" ] && kill -0 "$stale_pid" 2>/dev/null; then
        lifecycle_warn "Killing stale uvicorn (PID $stale_pid — alive but not serving)"
        kill "$stale_pid" 2>/dev/null || true
        sleep 1
    fi

    lifecycle_info "Starting Uvicorn server..."

    # ── توجيه الـ monolith إلى الخدمات المصغرة المحلية ──────────────────────
    # ORCHESTRATOR_SERVICE_URL: يُوجِّه OrchestratorClient إلى localhost:8006
    #   بدلاً من http://orchestrator-service:8006 (Docker DNS — لا يُحلّ في Gitpod).
    # CODESPACES=true: يُفعِّل apply_codespaces_local_overrides في AppSettings
    #   لضمان استخدام localhost لجميع الخدمات المصغرة.
    # ORCHESTRATOR_CHAT_ENDPOINT=state_graph: يُوجِّه إلى /api/chat/messages
    #   (StateGraph 13 عقدة) بدلاً من /agent/chat (OrchestratorAgent).
    export ORCHESTRATOR_SERVICE_URL="http://localhost:8006"
    export CODESPACES="true"
    export ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR="true"
    export ORCHESTRATOR_CHAT_ENDPOINT="${ORCHESTRATOR_CHAT_ENDPOINT:-state_graph}"
    export PLANNING_AGENT_URL="http://localhost:8002"
    export RESEARCH_AGENT_URL="http://localhost:8007"
    export REASONING_AGENT_URL="http://localhost:8008"
    export USER_SERVICE_URL="http://localhost:8001"
    lifecycle_info "Microservices routing: ORCHESTRATOR_SERVICE_URL=http://localhost:8006 (state_graph mode)"

    # ISS-091 (D-RELOAD-001 — 2026-05-27): --reload أُزيل من المسار الإنتاجي.
    # السبب الجذري لـ "kick → re-enter" في Codespaces:
    #   1. --reload يراقب كل .py في الـ repo. أي تعديل (commit hooks, agents,
    #      formatters, observability writes) → uvicorn يُعيد تشغيل الـ worker.
    #   2. عند إعادة التشغيل، كل WS connections تُقطع فوراً.
    #   3. المستخدم يرى: السؤال أُرسل → لا رد → التبديل لـ login screen.
    # القاعدة الجديدة: --reload فقط إذا DEV_RELOAD=1 صراحةً (محلي للمطورين).
    #
    # ISS-091 hotfix (2026-05-27): استخدام `local` خارج الـ function ⇒
    # bash يرفضه ⇒ supervisor يخرج عند Step 4 ⇒ frontend (5000) لا يبدأ.
    # هذا هو نفس بق ISS-037 — استخدم متغيراً عادياً (بدون local).
    reload_flag=""
    if [ "${DEV_RELOAD:-0}" = "1" ]; then
        reload_flag="--reload --reload-exclude .devcontainer/state/* --reload-exclude .observability/*"
        lifecycle_warn "DEV_RELOAD=1 — uvicorn --reload enabled (will kill WS connections on every .py edit)"
    fi

    # Start server in background — env vars already exported above
    # shellcheck disable=SC2086
    python -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port "$APP_PORT" \
        --ws websockets \
        --ws-ping-interval 20 \
        --ws-ping-timeout 30 \
        --timeout-keep-alive 75 \
        $reload_flag \
        --log-level info &

    UVICORN_PID=$!
    lifecycle_set_state "uvicorn_pid" "$UVICORN_PID"
    lifecycle_info "Uvicorn started (PID: $UVICORN_PID)"

    lifecycle_release_lock "uvicorn_launch"
fi

# ==============================================================================
# STEP 4B: Frontend Launch (Async - Non-Blocking)
# ==============================================================================

launch_frontend() {
    lifecycle_info "🚀 Frontend Launcher: Starting initialization..."

    if command -v npm >/dev/null 2>&1; then
        # ISS-101 (D-WS-PROXY-001): أعد التثبيت أيضاً عند تغيّر package.json
        # (مثلاً بعد git pull أضاف تبعية `ws`) — وليس فقط عند غياب node_modules.
        # وإلا تبقى التبعيات الجديدة غير مُثبَّتة و server.js قد ينهار.
        if [ ! -d "frontend/node_modules" ] || [ "frontend/package.json" -nt "frontend/node_modules" ]; then
            lifecycle_info "Frontend Launcher: Installing dependencies (this may take a while)..."
            if (cd frontend && npm install); then
                lifecycle_set_state "frontend_dependencies_installed" "$(date +%s)"
                lifecycle_info "Frontend Launcher: Dependencies installed successfully"
            else
                lifecycle_warn "Frontend Launcher: Dependency install failed"
                return 1
            fi
        fi

        # ISS-101 (D-WS-PROXY-001): ضمان حتمي لوجود `ws` الحقيقية — server.js يحتاجها
        # لوسيط الـ WebSocket. لا نعتمد على heuristic الـ mtime: نفحص require مباشرة،
        # ونثبّتها صراحةً إن غابت. (الاعتماد على نسخة Next المُجمَّعة قد لا يعمل بنمط
        # noServer → 1006). هذا يضمن أن proxy الـ WS يعمل في أول إقلاع.
        if ! (cd frontend && node -e "require('ws').WebSocketServer" >/dev/null 2>&1); then
            lifecycle_info "Frontend Launcher: ensuring 'ws' dependency (required by WS proxy)..."
            (cd frontend && npm install ws@^8.18.0 >/dev/null 2>&1) \
                && lifecycle_info "Frontend Launcher: 'ws' installed" \
                || lifecycle_warn "Frontend Launcher: 'ws' install failed (server.js will fall back)"
        fi

        # ISS-101 (D-WS-PROXY-002): امسح كاش بناء Next القديم إن كان مصدر الواجهة
        # أحدث منه. الـ Codespaces prebuilds قد تُخبّئ `.next` مبنياً من commit قديم،
        # فيُقدّم Next dev chunks قديمة للمتصفح (إصلاحات الواجهة لا تُحمَّل → الطرد
        # يستمر) رغم أن الكود على القرص جديد. مسحه يُجبر إعادة تجميع نظيفة.
        if [ -d "frontend/.next" ] && {
            [ "frontend/server.js" -nt "frontend/.next" ] ||
            [ "frontend/app/hooks/useRealtimeConnection.js" -nt "frontend/.next" ] ||
            [ "frontend/app/components/CogniForgeApp.jsx" -nt "frontend/.next" ]
        }; then
            lifecycle_info "Frontend Launcher: clearing stale .next build cache (source is newer)..."
            rm -rf "frontend/.next" 2>/dev/null || true
        fi

        if lifecycle_check_process "next.*dev\|node.*server\.js"; then
            lifecycle_info "Frontend Launcher: Next.js dev server already running"
        elif lsof -ti :"$FRONTEND_PORT" >/dev/null 2>&1; then
            lifecycle_warn "Frontend Launcher: Port $FRONTEND_PORT already in use — skipping start"
        else
            # D-WS-GITPOD-001: حذف stale lock قبل الإطلاق.
            # عند تعطل Next.js أو إيقافه بشكل مفاجئ، يبقى ملف .next/dev/lock
            # مقفلاً من العملية الميتة → يمنع إعادة التشغيل بخطأ "Unable to acquire lock".
            local next_lock="frontend/.next/dev/lock"
            if [ -f "$next_lock" ]; then
                lifecycle_info "Frontend Launcher: Removing stale Next.js dev lock..."
                rm -f "$next_lock" 2>/dev/null || true
            fi
            lifecycle_info "Frontend Launcher: Starting Next.js dev server on port $FRONTEND_PORT..."
            # D-WS-001: custom server يُمرِّر WebSocket إلى Gateway (8000)
            # next dev لا يُمرِّر WebSocket upgrades — server.js يحل هذا
            (cd frontend && PORT="$FRONTEND_PORT" HOSTNAME="0.0.0.0" exec npm run dev) &
            FRONTEND_PID=$!
            lifecycle_set_state "next_pid" "$FRONTEND_PID"
            lifecycle_info "Frontend Launcher: Next.js dev server started (PID: $FRONTEND_PID, port: $FRONTEND_PORT)"
        fi
    else
        lifecycle_warn "Frontend Launcher: npm not available"
    fi
}

if [ -f "frontend/package.json" ]; then
    lifecycle_info "Initializing Frontend in background (Async Mode)..."
    # Launch in background and don't wait
    launch_frontend >> "$APP_ROOT/.frontend_launcher.log" 2>&1 &
    lifecycle_info "✅ Frontend initialization offloaded to background process"
else
    lifecycle_info "Frontend directory not found - skipping Next.js startup"
fi

# ==============================================================================
# STEP 4C: Mission Control Launch (Grafana + Prometheus, native binaries)
# ==============================================================================
# Replaces the Docker-compose-based observability stack (which can't run in
# the default devcontainer — see CLAUDE.md §6.13/§6.16). Native binaries are
# baked into the runtime image at /opt/grafana and /opt/prometheus by the
# Dockerfile. No Docker daemon, no socket mount, no rebuild required.
# Runs in background, fully non-blocking. Failure does NOT block app boot.

launch_mission_control() {
    local OBS_LOG_DIR="$APP_ROOT/.observability"
    mkdir -p "$OBS_LOG_DIR"

    # ---- Hard guard: are the binaries actually present? -----------------
    if [ ! -x /opt/grafana/bin/grafana-server ] || [ ! -x /opt/prometheus/prometheus ]; then
        lifecycle_warn "Mission Control: native binaries missing at /opt/grafana or /opt/prometheus."
        lifecycle_warn "                  Image was built before §6.17. Rebuild the container to enable Mission Control."
        echo "[$(date -u +%FT%TZ)] binaries missing — Mission Control parked" \
            >> "$OBS_LOG_DIR/launch.log"
        return 0
    fi

    # ---- Already running? (idempotent) ----------------------------------
    if pgrep -f "/opt/prometheus/prometheus" >/dev/null 2>&1 \
       && pgrep -f "/opt/grafana/bin/grafana-server" >/dev/null 2>&1; then
        lifecycle_info "Mission Control: already running (skipping launch)."
        return 0
    fi

    # ---- Codespaces detection — wire Grafana to the preview proxy URL ----
    # Without this, Grafana's auth cookie has Domain=localhost and the
    # cross-origin proxy refuses it → infinite redirect (see §6.12).
    local public_url
    if [ -n "${CODESPACE_NAME:-}" ] && [ -n "${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN:-}" ]; then
        public_url="https://${CODESPACE_NAME}-3001.${GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN}/"
    elif [ -n "${CODESPACE_NAME:-}" ]; then
        public_url="https://${CODESPACE_NAME}-3001.preview.app.github.dev/"
    else
        public_url="http://localhost:3001/"
    fi

    if [[ "${public_url}" == https://* ]]; then
        export GF_SERVER_ROOT_URL="${public_url}"
        export GF_SERVER_DOMAIN="$(echo "${public_url}" | sed -E 's|^https?://([^/]+)/.*$|\1|')"
        export GF_SECURITY_COOKIE_SAMESITE="none"
        export GF_SECURITY_COOKIE_SECURE="true"
        export GF_SECURITY_CSRF_ALWAYS_CHECK="false"
    fi
    # Override port (grafana.ini default is 3000, we want 3001 to avoid
    # colliding with Next.js on 3000).
    export GF_SERVER_HTTP_PORT="3001"
    # Disable bundled plugin updates check — saves a network call at boot.
    export GF_PLUGINS_DISABLE_PLUGIN_UPDATES="true"
    # Anonymous viewer is enabled in grafana.ini; ensure admin password is
    # something the user can find (defaults to 'admin' on first boot).
    export GF_SECURITY_ADMIN_PASSWORD="${GF_SECURITY_ADMIN_PASSWORD:-cogniforge}"

    # ---- Persist resolved env for debug ---------------------------------
    {
        echo "# Generated by supervisor.sh @ $(date -u +%FT%TZ)"
        echo "MISSION_CONTROL_URL=${public_url}"
        [ -n "${GF_SERVER_ROOT_URL:-}" ]    && echo "GF_SERVER_ROOT_URL=${GF_SERVER_ROOT_URL}"
        [ -n "${GF_SERVER_DOMAIN:-}" ]      && echo "GF_SERVER_DOMAIN=${GF_SERVER_DOMAIN}"
        [ -n "${GF_SECURITY_COOKIE_SAMESITE:-}" ] && echo "GF_SECURITY_COOKIE_SAMESITE=${GF_SECURITY_COOKIE_SAMESITE}"
    } > "$OBS_LOG_DIR/grafana.env" 2>/dev/null || true

    # ---- Start Prometheus -----------------------------------------------
    lifecycle_info "Mission Control: starting Prometheus on :9090 ..."
    nohup /opt/prometheus/prometheus \
        --config.file=/app/observability/native/prometheus.yml \
        --storage.tsdb.path=/var/lib/prometheus \
        --storage.tsdb.retention.time=7d \
        --storage.tsdb.retention.size=512MB \
        --web.listen-address=0.0.0.0:9090 \
        --web.enable-lifecycle \
        > "$OBS_LOG_DIR/prometheus.log" 2>&1 &
    local prom_pid=$!
    lifecycle_set_state "prometheus_pid" "$prom_pid"

    # ---- Start Grafana --------------------------------------------------
    lifecycle_info "Mission Control: starting Grafana on :3001 ..."
    nohup /opt/grafana/bin/grafana-server \
        --config=/app/observability/grafana/grafana.ini \
        --homepath=/opt/grafana \
        cfg:default.paths.data=/var/lib/grafana \
        cfg:default.paths.logs=/var/log/grafana \
        cfg:default.paths.plugins=/var/lib/grafana/plugins \
        cfg:default.paths.provisioning=/app/observability/native/grafana/provisioning \
        > "$OBS_LOG_DIR/grafana.log" 2>&1 &
    local graf_pid=$!
    lifecycle_set_state "grafana_pid" "$graf_pid"

    lifecycle_info "Mission Control: launched (Prometheus pid=$prom_pid, Grafana pid=$graf_pid)"
    lifecycle_info "                  Public URL: ${public_url}"
}

# Launch in background — never block the supervisor on observability boot.
launch_mission_control >> "$APP_ROOT/.observability/launch.log" 2>&1 &
lifecycle_info "✅ Mission Control initialization offloaded to background"

# ==============================================================================
# STEP 4D: Orchestrator Service Launch (uvicorn process — no Docker required)
# ==============================================================================
# يُشغِّل orchestrator-service كـ uvicorn process مستقل على المنفذ 8006.
# يستخدم Supabase (DATABASE_URL الموجودة) عبر ORCHESTRATOR_DATABASE_URL.
# لا يتطلب Docker — يعمل مباشرة في Codespaces مثل Grafana و Prometheus.
# الفشل لا يوقف الـ supervisor — الخدمة تبدأ في وضع DEGRADED إذا فشل الـ DB.

launch_orchestrator_service() {
    local ORCH_LOG_DIR="$APP_ROOT/.observability"
    local ORCH_PORT="8006"
    local ORCH_HEALTH="http://localhost:${ORCH_PORT}/health"
    local ORCH_PID_FILE
    ORCH_PID_FILE=$(lifecycle_get_state "orchestrator_pid" 2>/dev/null || true)

    mkdir -p "$ORCH_LOG_DIR"

    # ── تحذير عند غياب OPENROUTER_API_KEY (لكن لا نوقف الإطلاق) ─────────────
    # D-WS-GITPOD-001: الـ orchestrator يعمل في DEGRADED mode بدون LLM key.
    # إيقاف الإطلاق كلياً يُسبب فشل /compose وانهيار Skills Pipeline.
    if [ -z "${OPENROUTER_API_KEY:-}" ]; then
        lifecycle_warn "Orchestrator: OPENROUTER_API_KEY not set — launching in DEGRADED mode (no LLM)."
        lifecycle_warn "             Set it in Gitpod Secrets or .devcontainer/secrets.env for full functionality."
        echo "[$(date -u +%FT%TZ)] OPENROUTER_API_KEY missing — orchestrator starting in DEGRADED mode" \
            >> "$ORCH_LOG_DIR/orchestrator.log"
    fi

    # ── idempotent: هل الخدمة تعمل بالفعل؟ ──────────────────────────────────
    if [ -n "$ORCH_PID_FILE" ] && kill -0 "$ORCH_PID_FILE" 2>/dev/null \
       && curl -sf --connect-timeout 2 "$ORCH_HEALTH" > /dev/null 2>&1; then
        lifecycle_info "Orchestrator: already running and healthy (PID $ORCH_PID_FILE)"
        return 0
    fi

    # ── إعداد ORCHESTRATOR_DATABASE_URL ──────────────────────────────────────
    # يستخدم Supabase (نفس DATABASE_URL للمونوليث) مع schema منفصل.
    # يمكن تجاوزه بـ ORCHESTRATOR_DATABASE_URL في secrets.env.
    # Fallback: SQLite في حالة غياب Postgres (sandbox/Codespaces firewall).
    local orch_db_url="${ORCHESTRATOR_DATABASE_URL:-${DATABASE_URL:-}}"
    if [ -z "$orch_db_url" ]; then
        lifecycle_warn "Orchestrator: no DATABASE_URL — using SQLite fallback (DEGRADED mode)."
        orch_db_url="sqlite+aiosqlite:///./orchestrator_dev.db"
    fi

    # ── تحويل URL إلى asyncpg (مطلوب لـ SQLAlchemy async) ────────────────────
    # SQLAlchemy create_async_engine يرفض psycopg2 المتزامن — يجب postgresql+asyncpg://
    # ISS-040: Supabase PgBouncer (port 6543) يرفض prepared statements حتى مع
    # statement_cache_size=0 في connect_args. الحل: استخدام port 5432 (direct
    # PostgreSQL connection) الذي يدعم prepared statements بشكل كامل.
    if [[ "$orch_db_url" != sqlite* ]]; then
        orch_db_url="${orch_db_url/postgresql:\/\//postgresql+asyncpg://}"
        orch_db_url="${orch_db_url/postgresql+psycopg2:\/\//postgresql+asyncpg://}"
        # تحويل port 6543 (PgBouncer) إلى 5432 (direct PostgreSQL) للـ orchestrator
        orch_db_url=$(echo "$orch_db_url" | sed 's/:6543\//:5432\//')
        # إزالة sslmode من URL — asyncpg يتعامل مع SSL عبر connect_args في database.py
        orch_db_url=$(echo "$orch_db_url" | sed 's/[?&]sslmode=[^&]*//' | sed 's/[?&]ssl=[^&]*//')
    fi

    lifecycle_info "Orchestrator: starting on :${ORCH_PORT} ..."

    # ── تشغيل uvicorn في الخلفية ──────────────────────────────────────────────
    # Step 4: OUTBOX_RELAY_ENABLED=true — تفعيل حلقة relay الدورية (D-031)
    # Step 9: PLANNING_AGENT_URL/RESEARCH_AGENT_URL/REASONING_AGENT_URL — Skills Pipeline
    # SECRET_KEY يجب أن يتطابق مع SECRET_KEY في الـ monolith لأن OrchestratorClient
    # يُولِّد JWT بـ SECRET_KEY الـ monolith ويُرسله إلى orchestrator للتحقق منه.
    # نستخدم نفس القيمة من .env أو المتغير البيئي لضمان التطابق.
    local shared_secret="${SECRET_KEY:-dev-secret-change-me}"
    ORCHESTRATOR_DATABASE_URL="$orch_db_url" \
    OPENROUTER_API_KEY="${OPENROUTER_API_KEY}" \
    TAVILY_API_KEY="${TAVILY_API_KEY:-}" \
    SECRET_KEY="${shared_secret}" \
    REDIS_URL="${REDIS_URL:-redis://localhost:6379}" \
    ENVIRONMENT="${ENVIRONMENT:-development}" \
    CODESPACES="true" \
    OUTBOX_RELAY_ENABLED="true" \
    OUTBOX_RELAY_INTERVAL_SECONDS="15" \
    OUTBOX_RELAY_BATCH_SIZE="50" \
    PLANNING_AGENT_URL="http://localhost:8002" \
    RESEARCH_AGENT_URL="http://localhost:8007" \
    REASONING_AGENT_URL="http://localhost:8008" \
    USER_SERVICE_URL="http://localhost:8001" \
    nohup python -m uvicorn microservices.orchestrator_service.main:app \
        --host 0.0.0.0 \
        --port "$ORCH_PORT" \
        --workers 1 \
        --log-level info \
        >> "$ORCH_LOG_DIR/orchestrator.log" 2>&1 &

    local orch_pid=$!
    lifecycle_set_state "orchestrator_pid" "$orch_pid"
    lifecycle_info "Orchestrator: launched (PID=$orch_pid) — health at $ORCH_HEALTH"
    lifecycle_info "             Logs: $ORCH_LOG_DIR/orchestrator.log"
}

# تشغيل في الخلفية — لا يحجب الـ supervisor
launch_orchestrator_service >> "$APP_ROOT/.observability/orchestrator.log" 2>&1 &
lifecycle_info "✅ Orchestrator Service initialization offloaded to background"

# ==============================================================================
# STEP 4E: User Service Launch (uvicorn process — no Docker required)
# ==============================================================================
# يُشغِّل user-service كـ uvicorn process مستقل على المنفذ 8001.
# Step 5: /metrics endpoint حقيقي بصيغة Prometheus (cogniforge_user_*).
# يستخدم Supabase (DATABASE_URL الموجودة) عبر USER_DATABASE_URL.
# الفشل لا يوقف الـ supervisor — الخدمة تبدأ في وضع DEGRADED إذا فشل الـ DB.

launch_user_service() {
    local USER_LOG_DIR="$APP_ROOT/.observability"
    local USER_PORT="8001"
    local USER_HEALTH="http://localhost:${USER_PORT}/health"

    mkdir -p "$USER_LOG_DIR"

    # ── التحقق من وجود DATABASE_URL ──────────────────────────────────────────
    local user_db_url="${USER_DATABASE_URL:-${DATABASE_URL:-}}"
    if [ -z "$user_db_url" ]; then
        lifecycle_warn "UserService: no DATABASE_URL — launching with SQLite fallback (DEGRADED)."
        user_db_url="sqlite+aiosqlite:///./user_service_dev.db"
    fi

    # ── idempotent: هل الخدمة تعمل بالفعل؟ ──────────────────────────────────
    if pgrep -f "uvicorn microservices.user_service" > /dev/null 2>&1 \
       && curl -sf --connect-timeout 2 "$USER_HEALTH" > /dev/null 2>&1; then
        lifecycle_info "UserService: already running and healthy on :${USER_PORT}"
        return 0
    fi

    # ── إيقاف أي نسخة قديمة ──────────────────────────────────────────────────
    pkill -f "uvicorn microservices.user_service" 2>/dev/null || true
    sleep 1

    lifecycle_info "UserService: starting on :${USER_PORT} (Step 5 — /metrics active)..."

    # ── تشغيل uvicorn في الخلفية ──────────────────────────────────────────────
    # D-WS-SECRET-KEY-001 (2026-05-26): SECRET_KEY يجب أن يتطابق مع monolith.
    # سبب الكارثة: user-service كان يستخدم default `cogniforge-user-service-dev-key`
    # بينما monolith يستخدم `dev-secret-change-me`. النتيجة:
    #   - login → user-service يُوقّع token بـ key A
    #   - WS handshake → monolith يُحاول التحقق بـ key B → 4401
    # الحل: استخدم نفس shared_secret (الـ monolith default) كـ fallback.
    # نُصدِّر USER_SECRET_KEY أيضاً كحماية إضافية ضد any pydantic-settings quirks
    # حول env_prefix vs validation_alias.
    local shared_user_secret="${SECRET_KEY:-dev-secret-change-me}"
    USER_DATABASE_URL="$user_db_url" \
    SECRET_KEY="${shared_user_secret}" \
    USER_SECRET_KEY="${shared_user_secret}" \
    ENVIRONMENT="${ENVIRONMENT:-development}" \
    USER_SERVICE_NAME="user-service" \
    USER_SERVICE_VERSION="1.0.0" \
    nohup python -m uvicorn microservices.user_service.main:app \
        --host 0.0.0.0 \
        --port "$USER_PORT" \
        --workers 1 \
        --log-level info \
        >> "$USER_LOG_DIR/user_service.log" 2>&1 &

    local user_pid=$!
    lifecycle_info "UserService: launched (PID=$user_pid) — health at $USER_HEALTH"
    lifecycle_info "            Logs: $USER_LOG_DIR/user_service.log"
}

# تشغيل في الخلفية — لا يحجب الـ supervisor
launch_user_service >> "$APP_ROOT/.observability/user_service.log" 2>&1 &
lifecycle_info "✅ User Service initialization offloaded to background"

# ==============================================================================
# STEP 4F: Planning Agent Launch (uvicorn process — no Docker required)
# ==============================================================================
# يُشغِّل planning-agent كـ uvicorn process مستقل على المنفذ 8002.
# Step 6: /metrics endpoint حقيقي بصيغة Prometheus (cogniforge_planning_*).
# يستخدم Supabase (DATABASE_URL الموجودة) عبر PLANNING_DATABASE_URL.
# يتطلب OPENROUTER_API_KEY لتفعيل DSPy/LangGraph — يعمل بخطة احتياطية بدونه.
# الفشل لا يوقف الـ supervisor — الخدمة تبدأ في وضع DEGRADED إذا فشل الـ DB.

launch_planning_agent() {
    local PLANNING_LOG_DIR="$APP_ROOT/.observability"
    local PLANNING_PORT="8002"
    local PLANNING_HEALTH="http://localhost:${PLANNING_PORT}/health"

    mkdir -p "$PLANNING_LOG_DIR"

    # ── التحقق من وجود DATABASE_URL ──────────────────────────────────────────
    local planning_db_url="${PLANNING_DATABASE_URL:-${DATABASE_URL:-}}"
    if [ -z "$planning_db_url" ]; then
        lifecycle_warn "PlanningAgent: no DATABASE_URL — launching with SQLite fallback (DEGRADED)."
        planning_db_url="sqlite+aiosqlite:///./planning_agent_dev.db"
    fi

    # ── تحويل URL إلى asyncpg (مطلوب لـ SQLAlchemy async) ────────────────────
    # SQLAlchemy create_async_engine يرفض psycopg2 المتزامن — يجب postgresql+asyncpg://
    planning_db_url="${planning_db_url/postgresql:\/\//postgresql+asyncpg://}"
    planning_db_url="${planning_db_url/postgresql+psycopg2:\/\//postgresql+asyncpg://}"
    # ISS-040: Supabase PgBouncer (port 6543) يرفض prepared statements — نستخدم 5432 مباشرة
    planning_db_url=$(echo "$planning_db_url" | sed 's/:6543\//:5432\//')
    # إزالة sslmode من URL — asyncpg لا يقبله في query string
    planning_db_url=$(echo "$planning_db_url" | sed 's/[?&]sslmode=[^&]*//' | sed 's/[?&]ssl=[^&]*//')

    # ── idempotent: هل الخدمة تعمل بالفعل؟ ──────────────────────────────────
    if pgrep -f "uvicorn microservices.planning_agent" > /dev/null 2>&1 \
       && curl -sf --connect-timeout 2 "$PLANNING_HEALTH" > /dev/null 2>&1; then
        lifecycle_info "PlanningAgent: already running and healthy on :${PLANNING_PORT}"
        return 0
    fi

    # ── إيقاف أي نسخة قديمة ──────────────────────────────────────────────────
    pkill -f "uvicorn microservices.planning_agent" 2>/dev/null || true
    sleep 1

    lifecycle_info "PlanningAgent: starting on :${PLANNING_PORT} (Step 6 — /metrics active)..."

    # ── تشغيل uvicorn في الخلفية ──────────────────────────────────────────────
    # ISS-042 (Step 11): SECRET_KEY يجب أن يتطابق مع orchestrator لقبول X-Service-Token
    # planning-agent يقرأ SECRET_KEY (validation_alias) — ليس PLANNING_SECRET_KEY
    # D-WS-SECRET-KEY-001 (2026-05-26): default يجب أن يطابق monolith — `dev-secret-change-me`.
    # كان `super_secret_key_change_in_production` يُسبب فشل X-Service-Token verification
    # بين orchestrator (`dev-secret-change-me`) و planning-agent → Skills Pipeline fails.
    local shared_planning_secret="${SECRET_KEY:-dev-secret-change-me}"
    PLANNING_DATABASE_URL="$planning_db_url" \
    OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    PLANNING_OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    SECRET_KEY="${shared_planning_secret}" \
    PLANNING_SECRET_KEY="${shared_planning_secret}" \
    PLANNING_ENVIRONMENT="${ENVIRONMENT:-development}" \
    PLANNING_SERVICE_NAME="planning-agent" \
    PLANNING_SERVICE_VERSION="1.0.0" \
    nohup python -m uvicorn microservices.planning_agent.main:app \
        --host 0.0.0.0 \
        --port "$PLANNING_PORT" \
        --workers 1 \
        --log-level info \
        >> "$PLANNING_LOG_DIR/planning_agent.log" 2>&1 &

    local planning_pid=$!
    lifecycle_info "PlanningAgent: launched (PID=$planning_pid) — health at $PLANNING_HEALTH"
    lifecycle_info "             Logs: $PLANNING_LOG_DIR/planning_agent.log"
}

# تشغيل في الخلفية — لا يحجب الـ supervisor
launch_planning_agent >> "$APP_ROOT/.observability/planning_agent.log" 2>&1 &
lifecycle_info "✅ Planning Agent initialization offloaded to background"

# ==============================================================================
# STEP 4G: Research Agent Launch (uvicorn process — no Docker required)
# ==============================================================================
# يُشغِّل research-agent كـ uvicorn process مستقل على المنفذ 8007.
# Step 7: /metrics endpoint حقيقي + Tavily web search حي عند توفر TAVILY_API_KEY.
# يبدأ تلقائياً عند توفر DATABASE_URL. Tavily اختياري — الخدمة تعمل بدونه.
# ==============================================================================

launch_research_agent() {
    local RESEARCH_PORT="8007"
    local RESEARCH_HEALTH="http://localhost:${RESEARCH_PORT}/health"
    local RESEARCH_LOG_DIR="$APP_ROOT/.observability"
    local RESEARCH_LOG="$RESEARCH_LOG_DIR/research_agent.log"

    mkdir -p "$RESEARCH_LOG_DIR"

    # ── تحذير عند غياب DATABASE_URL (لكن لا نوقف الإطلاق) ───────────────────
    # Research Agent يعمل بدون DB — يستخدم Tavily فقط.
    if [ -z "${DATABASE_URL:-}" ]; then
        lifecycle_warn "Research Agent: DATABASE_URL not set — launching anyway (Tavily-only mode)."
    fi

    # ── idempotent: تجنب إطلاق نسخة ثانية ───────────────────────────────────
    if pgrep -f "research_agent.main:app.*${RESEARCH_PORT}" > /dev/null 2>&1; then
        lifecycle_info "Research Agent: already running on :${RESEARCH_PORT} — skipping"
        return 0
    fi

    # ── تحويل DATABASE_URL إلى asyncpg (ISS-038-B) ───────────────────────────
    local _raw_db="${RESEARCH_DATABASE_URL:-${DATABASE_URL:-}}"
    local _async_db="${_raw_db/postgresql:\/\//postgresql+asyncpg://}"
    # ISS-040: Supabase PgBouncer (port 6543) → direct PostgreSQL (port 5432)
    _async_db=$(echo "$_async_db" | sed 's/:6543\//:5432\//')
    _async_db=$(echo "$_async_db" | sed 's/[?&]sslmode=[^&]*//')

    lifecycle_info "Research Agent: launching uvicorn on :${RESEARCH_PORT}..."

    # D-WS-SECRET-KEY-001 (2026-05-26): Skills Pipeline JWT consistency.
    # research-agent verifies X-Service-Token signed by orchestrator
    # (which defaults to `dev-secret-change-me`). Mismatched defaults break
    # the Skills Pipeline silently → chat falls back to local_graph.
    local shared_research_secret="${SECRET_KEY:-dev-secret-change-me}"

    # ISS-042 (Step 11): TAVILY_API_KEY و OPENROUTER_API_KEY مُحقَنان صراحةً
    RESEARCH_DATABASE_URL="$_async_db" \
    RESEARCH_OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    TAVILY_API_KEY="${TAVILY_API_KEY:-}" \
    ENVIRONMENT="${ENVIRONMENT:-development}" \
    SECRET_KEY="${shared_research_secret}" \
    RESEARCH_SECRET_KEY="${shared_research_secret}" \
    PYTHONPATH="$APP_ROOT" \
    nohup python -m uvicorn microservices.research_agent.main:app \
        --host 0.0.0.0 \
        --port "$RESEARCH_PORT" \
        --log-level info \
        --no-access-log \
        >> "$RESEARCH_LOG" 2>&1 &

    local research_pid=$!
    lifecycle_info "Research Agent: launched (PID=$research_pid) — health at $RESEARCH_HEALTH"
    lifecycle_info "             Logs: $RESEARCH_LOG"
    lifecycle_info "             Tavily: ${TAVILY_API_KEY:+✅ KEY SET}${TAVILY_API_KEY:-❌ no key — web search disabled}"
}

# تشغيل في الخلفية — لا يحجب الـ supervisor
launch_research_agent >> "$APP_ROOT/.observability/research_agent.log" 2>&1 &
lifecycle_info "✅ Research Agent initialization offloaded to background"

# ==============================================================================
# STEP 4H: Reasoning Agent (الخطوة 8 — MCTS + LLM + /metrics)
# ==============================================================================

launch_reasoning_agent() {
    local REASONING_PORT="8008"
    local REASONING_HEALTH="http://localhost:${REASONING_PORT}/health"
    local REASONING_LOG_DIR="$APP_ROOT/.observability"
    local REASONING_LOG="$REASONING_LOG_DIR/reasoning_agent.log"

    mkdir -p "$REASONING_LOG_DIR"

    # ── تحذير عند غياب DATABASE_URL (لكن لا نوقف الإطلاق) ───────────────────
    # Reasoning Agent يعمل بدون DB — يستخدم MCTS + LLM فقط.
    if [ -z "${DATABASE_URL:-}" ]; then
        lifecycle_warn "Reasoning Agent: DATABASE_URL not set — launching anyway (MCTS-only mode)."
    fi

    # ── idempotent: تجنب إطلاق نسخة ثانية ───────────────────────────────────
    if pgrep -f "reasoning_agent.main:app.*${REASONING_PORT}" > /dev/null 2>&1; then
        lifecycle_info "Reasoning Agent: already running on :${REASONING_PORT} — skipping"
        return 0
    fi

    lifecycle_info "Reasoning Agent: launching uvicorn on :${REASONING_PORT}..."
    lifecycle_info "             LLM: ${OPENROUTER_API_KEY:+✅ OpenRouter}${OPENROUTER_API_KEY:-⚠️  mock mode (no OPENROUTER_API_KEY)}"

    # D-WS-SECRET-KEY-001 (2026-05-26): Skills Pipeline JWT consistency.
    # reasoning-agent verifies X-Service-Token signed by orchestrator
    # (which defaults to `dev-secret-change-me`). Mismatched defaults break
    # the Skills Pipeline silently → chat falls back to local_graph.
    local shared_reasoning_secret="${SECRET_KEY:-dev-secret-change-me}"

    # ISS-042 (Step 11): OPENROUTER_API_KEY مُحقَن صراحةً لتفعيل LLM الحقيقي
    REASONING_OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    OPENAI_API_KEY="${OPENAI_API_KEY:-}" \
    ENVIRONMENT="${ENVIRONMENT:-development}" \
    SECRET_KEY="${shared_reasoning_secret}" \
    REASONING_SECRET_KEY="${shared_reasoning_secret}" \
    PYTHONPATH="$APP_ROOT" \
    nohup python -m uvicorn microservices.reasoning_agent.main:app \
        --host 0.0.0.0 \
        --port "$REASONING_PORT" \
        --log-level info \
        --no-access-log \
        >> "$REASONING_LOG" 2>&1 &

    local reasoning_pid=$!
    lifecycle_info "Reasoning Agent: launched (PID=$reasoning_pid) — health at $REASONING_HEALTH"
    lifecycle_info "             Logs: $REASONING_LOG"
}

# تشغيل في الخلفية — لا يحجب الـ supervisor
launch_reasoning_agent >> "$APP_ROOT/.observability/reasoning_agent.log" 2>&1 &
lifecycle_info "✅ Reasoning Agent initialization offloaded to background"

# ==============================================================================
# STEP 4I: Content Retrieval Skill (الخطوة 11 — Skill مستقلة + /metrics)
# ==============================================================================
# يُشغِّل content-retrieval-skill كـ uvicorn process مستقل على المنفذ 8009.
# Step 11: intent_classifier + retrieval_engine + /metrics (cogniforge_retrieval_*).
# لا يتطلب DB — يقرأ من knowledge_base/ مباشرة.
# ISS-042: إصلاح Service Token + DSPy 3.x + parallel pipeline.
# ==============================================================================

launch_content_retrieval_skill() {
    local RETRIEVAL_PORT="8009"
    local RETRIEVAL_HEALTH="http://localhost:${RETRIEVAL_PORT}/health"
    local RETRIEVAL_LOG_DIR="$APP_ROOT/.observability"
    local RETRIEVAL_LOG="$RETRIEVAL_LOG_DIR/content_retrieval_skill.log"

    mkdir -p "$RETRIEVAL_LOG_DIR"

    # ── idempotent: تجنب إطلاق نسخة ثانية ───────────────────────────────────
    if pgrep -f "content_retrieval_skill.main:app" > /dev/null 2>&1; then
        lifecycle_info "Content Retrieval Skill: already running on :${RETRIEVAL_PORT} — skipping"
        return 0
    fi

    lifecycle_info "Content Retrieval Skill: launching uvicorn on :${RETRIEVAL_PORT} (Step 11)..."

    KB_ROOT="${APP_ROOT}/knowledge_base" \
    OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    TAVILY_API_KEY="${TAVILY_API_KEY:-}" \
    ENVIRONMENT="${ENVIRONMENT:-development}" \
    PYTHONPATH="$APP_ROOT" \
    python -m uvicorn microservices.content_retrieval_skill.main:app \
        --host 0.0.0.0 \
        --port "$RETRIEVAL_PORT" \
        --log-level info \
        --no-access-log \
        >> "$RETRIEVAL_LOG" 2>&1 &

    local retrieval_pid=$!
    lifecycle_info "Content Retrieval Skill: launched (PID=$retrieval_pid) — health at $RETRIEVAL_HEALTH"
    lifecycle_info "             Logs: $RETRIEVAL_LOG"
    lifecycle_info "             KB: ${APP_ROOT}/knowledge_base"
}

# تشغيل في الخلفية — لا يحجب الـ supervisor
launch_content_retrieval_skill >> "$APP_ROOT/.observability/content_retrieval_skill.log" 2>&1 &
lifecycle_info "✅ Content Retrieval Skill initialization offloaded to background"

# ==============================================================================
# STEP 4J: Conversation Service (الخطوة 12 — LangGraph StateGraph + /metrics)
# ==============================================================================
# يُشغِّل conversation-service كـ uvicorn process مستقل على المنفذ 8003.
# Step 12: LangGraph StateGraph (intent_node → response_node) + Prometheus metrics.
# يتطلب DATABASE_URL للـ DB (اختياري — fallback لـ SQLite).
# يعمل بدون OPENROUTER_API_KEY (deterministic fallback responses).
# ==============================================================================

launch_conversation_service() {
    local CONV_PORT="8003"
    local CONV_HEALTH="http://localhost:${CONV_PORT}/health"
    local CONV_LOG_DIR="$APP_ROOT/.observability"
    local CONV_LOG="$CONV_LOG_DIR/conversation_service.log"

    mkdir -p "$CONV_LOG_DIR"

    # ── idempotent: تجنب إطلاق نسخة ثانية ───────────────────────────────────
    if pgrep -f "conversation_service.main:app" > /dev/null 2>&1; then
        lifecycle_info "Conversation Service: already running on :${CONV_PORT} — skipping"
        return 0
    fi

    lifecycle_info "Conversation Service: launching uvicorn on :${CONV_PORT} (Step 12)..."

    # تحويل DATABASE_URL إلى postgresql+asyncpg:// (ISS-038-B)
    local CONV_DB_URL="${DATABASE_URL:-sqlite+aiosqlite:///:memory:}"
    CONV_DB_URL="${CONV_DB_URL/postgresql:\/\//postgresql+asyncpg:\/\/}"
    CONV_DB_URL="${CONV_DB_URL/postgres:\/\//postgresql+asyncpg:\/\/}"
    # استخدام port 5432 (direct PG) بدلاً من 6543 (PgBouncer) — ISS-040
    CONV_DB_URL="${CONV_DB_URL/:6543\//:5432/}"
    # إزالة sslmode من URL (asyncpg يتعامل معه عبر connect_args)
    CONV_DB_URL=$(echo "$CONV_DB_URL" | sed 's/?sslmode=[^&]*//;s/&sslmode=[^&]*//')

    CONV_DATABASE_URL="$CONV_DB_URL" \
    OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
    ENVIRONMENT="${ENVIRONMENT:-development}" \
    PYTHONPATH="$APP_ROOT" \
    python -m uvicorn microservices.conversation_service.main:app \
        --host 0.0.0.0 \
        --port "$CONV_PORT" \
        --ws websockets \
        --ws-ping-interval 20 \
        --ws-ping-timeout 30 \
        --timeout-keep-alive 75 \
        --log-level info \
        --no-access-log \
        >> "$CONV_LOG" 2>&1 &

    local conv_pid=$!
    lifecycle_info "Conversation Service: launched (PID=$conv_pid) — health at $CONV_HEALTH"
    lifecycle_info "             Logs: $CONV_LOG"
    lifecycle_info "             DB: ${CONV_DB_URL:0:40}..."
}

# تشغيل في الخلفية — لا يحجب الـ supervisor
launch_conversation_service >> "$APP_ROOT/.observability/conversation_service.log" 2>&1 &
lifecycle_info "✅ Conversation Service initialization offloaded to background"

# ==============================================================================
# STEP 5: Health Check & Readiness (فحص الصحة والجاهزية)
# ==============================================================================

lifecycle_info "Step 5/5: Health check and readiness verification..."

# ── Always re-verify health — never trust stale state files ──────────────────
# The state file app_healthy may be set from a previous successful run.
# If uvicorn crashed on import (e.g. missing DATABASE_URL), the port is not
# listening even though the PID is alive. We must probe the actual endpoint.
# ─────────────────────────────────────────────────────────────────────────────

# CODESPACES / Gitpod: Longer timeout for cloud environments
if [ -n "${CODESPACES:-}" ] || [ -n "${GITPOD_WORKSPACE_ID:-}" ]; then
    PORT_TIMEOUT=90
    HEALTH_TIMEOUT=120
    lifecycle_info "Cloud environment detected — using extended timeouts (port: ${PORT_TIMEOUT}s, health: ${HEALTH_TIMEOUT}s)"
else
    PORT_TIMEOUT=60
    HEALTH_TIMEOUT=30
fi

# Wait for BACKEND port
if ! lifecycle_wait_for_port "$APP_PORT" "$PORT_TIMEOUT"; then
    lifecycle_warn "Backend port $APP_PORT did not open within ${PORT_TIMEOUT}s"
    lifecycle_warn "Possible causes:"
    lifecycle_warn "  1. DATABASE_URL missing or invalid — check .env"
    lifecycle_warn "  2. Import error in app/main.py — check uvicorn log"
    lifecycle_warn "  3. Port already in use by another process"
    lifecycle_warn "Supervisor continuing in DEGRADED mode (Grafana + Prometheus still running)"
    lifecycle_set_state "app_healthy" "degraded"
    lifecycle_set_state "app_ready" "false"
    # Do NOT exit — Grafana and Prometheus are still useful even without FastAPI
else
    # Port is open — verify the health endpoint responds correctly
    lifecycle_info "Performing backend health check..."
    health_response=$(curl -sf --connect-timeout 5 "$HEALTH_ENDPOINT" 2>/dev/null || echo "{}")

    if echo "$health_response" | grep -q '"application":"ok"'; then
        lifecycle_info "✅ Backend is healthy and ready!"
        lifecycle_set_state "app_healthy" "$(date +%s)"
        lifecycle_set_state "app_ready" "true"
    else
        lifecycle_warn "Health endpoint responded but application is not ok: $health_response"
        lifecycle_set_state "app_healthy" "degraded"
        lifecycle_set_state "app_ready" "false"
    fi
fi

# ==============================================================================
# COMPLETION (الإكمال)
# ==============================================================================

lifecycle_info "═══════════════════════════════════════════════════════"
lifecycle_info "🎉 Application Lifecycle Complete"
lifecycle_info "═══════════════════════════════════════════════════════"
lifecycle_info ""
_app_ready=$(lifecycle_get_state "app_ready" 2>/dev/null || echo "false")
if [ "$_app_ready" = "true" ]; then
    lifecycle_info "✅ All Systems Operational"
else
    lifecycle_info "⚠️  DEGRADED MODE — Backend not healthy (check .env DATABASE_URL)"
fi
lifecycle_info "   • Dependencies: Installed"
lifecycle_info "   • Database: Migrated"
lifecycle_info "   • Admin User: Seeded"
lifecycle_info "   • Backend Server: port $APP_PORT (ready=$_app_ready)"
lifecycle_info "   • Orchestrator Service: port 8006 (background — check .observability/orchestrator.log)"
lifecycle_info "   • User Service:         port 8001 (background — check .observability/user_service.log)"
lifecycle_info "   • Planning Agent:       port 8002 (background — check .observability/planning_agent.log)"
lifecycle_info "   • Research Agent:       port 8007 (background — check .observability/research_agent.log)"
lifecycle_info "   • Grafana: port 3001 (Mission Control)"
lifecycle_info "   • Prometheus: port 9090"
lifecycle_info ""
lifecycle_info "⏳ Frontend Status:"
lifecycle_info "   • Initialization is running in BACKGROUND."
lifecycle_info "   • It may take a few more minutes to appear on port $FRONTEND_PORT."
lifecycle_info "   • Frontend Logs: .frontend_launcher.log"
lifecycle_info ""
lifecycle_info "🚀 CLICK HERE TO LOGIN:"
lifecycle_info "   http://localhost:$APP_PORT (API)"
lifecycle_info "   http://localhost:$FRONTEND_PORT (Web - Wait for it)"
lifecycle_info ""
lifecycle_info "📊 System Status:"
lifecycle_info "   • Uptime: $(uptime -p 2>/dev/null || echo 'N/A')"
lifecycle_info "   • Memory: $(free -h 2>/dev/null | awk '/^Mem:/ {print $3 "/" $2}' || echo 'N/A')"
lifecycle_info "   • Processes: $(ps aux | wc -l) running"
lifecycle_info "═══════════════════════════════════════════════════════"

# Keep supervisor running to maintain state
lifecycle_info "Supervisor entering monitoring mode..."

# ── دالة إعادة تشغيل uvicorn مع المتغيرات الصحيحة ──────────────────────────
_restart_uvicorn() {
    lifecycle_warn "Restarting uvicorn main app..."

    # أوقف أي instance قديم
    local old_pid
    old_pid=$(lifecycle_get_state "uvicorn_pid" 2>/dev/null || true)
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
        kill "$old_pid" 2>/dev/null || true
        sleep 2
    fi

    # ISS-091 (D-SECRET-002 — 2026-05-27): إعادة تأكيد SECRET_KEY قبل إطلاق
    # uvicorn — defensive في حالة فقدان env بين supervisor instances.
    local state_key_file="$APP_ROOT/.devcontainer/state/dev_secret_key"
    if [ -z "${SECRET_KEY:-}" ] || [ "${#SECRET_KEY}" -lt 32 ] \
       || [ "${SECRET_KEY}" = "dev-secret-change-me" ]; then
        if [ -f "$state_key_file" ]; then
            local stored_key
            stored_key=$(cat "$state_key_file" 2>/dev/null | tr -d '[:space:]')
            if [ -n "$stored_key" ] && [ "${#stored_key}" -ge 32 ]; then
                export SECRET_KEY="$stored_key"
                lifecycle_info "_restart_uvicorn: SECRET_KEY reloaded from state file (${#stored_key} chars)"
            fi
        fi
    fi

    # تأكد من وجود المتغيرات الأساسية
    export ORCHESTRATOR_SERVICE_URL="http://localhost:8006"
    export CODESPACES="true"
    export ALLOW_CONTAINER_LOCALHOST_ORCHESTRATOR="true"
    export ORCHESTRATOR_CHAT_ENDPOINT="${ORCHESTRATOR_CHAT_ENDPOINT:-state_graph}"
    export PLANNING_AGENT_URL="http://localhost:8002"
    export RESEARCH_AGENT_URL="http://localhost:8007"
    export REASONING_AGENT_URL="http://localhost:8008"
    export USER_SERVICE_URL="http://localhost:8001"

    # ISS-091 (D-RELOAD-001): --reload أُزيل (يُفعَّل عبر DEV_RELOAD=1 فقط).
    local reload_flag=""
    if [ "${DEV_RELOAD:-0}" = "1" ]; then
        reload_flag="--reload --reload-exclude .devcontainer/state/* --reload-exclude .observability/*"
    fi

    # shellcheck disable=SC2086
    python -m uvicorn app.main:app \
        --host 0.0.0.0 \
        --port "$APP_PORT" \
        --ws websockets \
        --ws-ping-interval 20 \
        --ws-ping-timeout 30 \
        --timeout-keep-alive 75 \
        $reload_flag \
        --log-level info &

    local new_pid=$!
    lifecycle_set_state "uvicorn_pid" "$new_pid"
    lifecycle_info "Uvicorn restarted (PID: $new_pid)"
}

# ISS-100 (D-HEALTH-002 — 2026-05-29): "Degraded ≠ Dead" — لا تُعِد تشغيل uvicorn
# لمجرّد أن قاعدة البيانات متعثّرة.
#
# الكارثة المُصلَحة (flapping + لا إجابة): الـ `/health` يُرجع HTTP 503 عندما تكون
# Supabase غير قابلة للوصول مؤقتاً (مع أن جسم الرد يقول `"application":"ok"`).
# المراقب القديم كان يَعدّ أي رمز ≠ 200 فشلاً → بعد 3 → يُعيد تشغيل uvicorn.
# لكن إعادة تشغيل uvicorn **لا تُصلح** خللاً في Supabase — بل تُسقط **كل**
# اتصالات الـ WebSocket النشطة (تأرجح متصل/غير متصل) وتقطع الإجابات الجارية
# (لا يرد عن الأسئلة)، ثم يتكرر الفشل → حلقة إعادة تشغيل كارثية.
#
# الإصلاح: نُعيد التشغيل **فقط** عندما يكون التطبيق ميتاً فعلاً (لا استجابة /
# رفض اتصال). أي استجابة تحمل `"application":"ok"` (حتى 503 بسبب DB) = التطبيق
# حيّ ومتدهور → نتركه يعمل (لا نقتل اتصالات المستخدمين).
_app_is_alive() {
    local timeout="${1:-15}"
    command -v curl >/dev/null 2>&1 || return 1
    local resp code body
    resp=$(curl -s -m "$timeout" -w $'\n%{http_code}' "$HEALTH_ENDPOINT" 2>/dev/null || printf '\n000')
    code="${resp##*$'\n'}"
    body="${resp%$'\n'*}"
    # 200 = صحّة كاملة.
    [ "$code" = "200" ] && return 0
    # أي استجابة من طبقة التطبيق (حتى 503 بسبب DB) = حيّ لكن متدهور → لا تُعِد التشغيل.
    if printf '%s' "$body" | grep -q '"application"[[:space:]]*:[[:space:]]*"ok"'; then
        return 0
    fi
    # لا استجابة قابلة للاستخدام (000 / رفض اتصال / 5xx بلا application:ok) → ميت.
    return 1
}

# ISS-091 (D-HEALTH-001 — 2026-05-27): tolerant monitoring loop.
# قبل: 5s timeout + 1 فشل → restart. ⇒ كل blip في Supabase response time يقتل
# WS connections النشطة (هذا حدث في كل session نشطة من المستخدم).
# بعد:
#   - 15s timeout (Supabase free tier يصل لـ 8-12s تحت الحمل)
#   - 3 إخفاقات متتالية مطلوبة قبل restart
#   - intervals بين الفحوصات 30s
#   - D-HEALTH-002: إعادة التشغيل تُحسب فقط عند موت التطبيق فعلاً، لا عند تدهور DB.
HEALTH_TIMEOUT_SECS="${HEALTH_TIMEOUT_SECS:-15}"
HEALTH_FAILURE_THRESHOLD="${HEALTH_FAILURE_THRESHOLD:-3}"
HEALTH_INTERVAL_SECS="${HEALTH_INTERVAL_SECS:-30}"
_health_consecutive_failures=0

# Monitor application LIVENESS — restart uvicorn only after N consecutive DEATHS.
while true; do
    sleep "$HEALTH_INTERVAL_SECS"

    if lifecycle_check_http "$HEALTH_ENDPOINT" 200 "$HEALTH_TIMEOUT_SECS"; then
        if [ "$_health_consecutive_failures" -gt 0 ]; then
            lifecycle_info "Health check recovered after $_health_consecutive_failures failure(s)"
        fi
        _health_consecutive_failures=0
        lifecycle_set_state "app_healthy" "true"
    elif _app_is_alive "$HEALTH_TIMEOUT_SECS"; then
        # D-HEALTH-002: التطبيق حيّ لكن متدهور (DB blip غالباً). إعادة التشغيل لن
        # تُصلح ذلك وستُسقط كل اتصالات الـ WebSocket — لذا لا نُعيد التشغيل ولا
        # نَعدّ هذا موتاً. نُصفّر عدّاد الموت لأن العملية حيّة.
        if [ "$_health_consecutive_failures" -gt 0 ]; then
            lifecycle_info "App alive but degraded (DB?) — NOT restarting (D-HEALTH-002)"
        else
            lifecycle_warn "Health degraded (non-200) but app alive — NOT restarting (D-HEALTH-002)"
        fi
        _health_consecutive_failures=0
    else
        _health_consecutive_failures=$((_health_consecutive_failures + 1))
        lifecycle_warn "App UNREACHABLE (consecutive=$_health_consecutive_failures/$HEALTH_FAILURE_THRESHOLD)"
        if [ "$_health_consecutive_failures" -ge "$HEALTH_FAILURE_THRESHOLD" ]; then
            lifecycle_warn "App death threshold reached — restarting uvicorn"
            lifecycle_clear_state "app_healthy"
            _restart_uvicorn
            _health_consecutive_failures=0
            # انتظر حتى يبدأ uvicorn الجديد
            sleep 15
            if _app_is_alive "$HEALTH_TIMEOUT_SECS"; then
                lifecycle_info "Uvicorn recovered successfully"
                lifecycle_set_state "app_healthy" "true"
            else
                lifecycle_warn "Uvicorn restart did not recover — will retry next cycle"
            fi
        fi
    fi
done
