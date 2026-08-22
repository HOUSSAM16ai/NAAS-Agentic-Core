# ✅ GitHub Actions Verification Checklist

## Pre-Push Verification

Before pushing to GitHub, ensure all these checks pass locally:

### 1. Code Quality
```bash
# Ruff linting
ruff check .
# Expected: All checks passed!

# Ruff formatting
ruff format --check .
# Expected: X files already formatted
```

### 2. Tests
```bash
# Run core tests
DATABASE_URL="sqlite+aiosqlite:///:memory:" \
SECRET_KEY="test" \
ENVIRONMENT="testing" \
LLM_MOCK_MODE="1" \
SUPABASE_URL="https://dummy.supabase.co" \
SUPABASE_SERVICE_ROLE_KEY="dummy" \
python -m pytest tests/test_api_crud.py tests/test_admin_auth_config_fix.py -v
# Expected: All tests passed
```

### 3. Complexity Check
```bash
# Check function complexity
radon cc app/ -a -s | grep "Average complexity"
# Expected: Average complexity: A or B
```

### 4. Git Status
```bash
git status
# Expected: working tree clean
```

## Post-Push Monitoring

After pushing, monitor GitHub Actions:

1. Visit: https://github.com/Houssam-lab/NAAS-Agentic-Core/actions
2. Check latest workflow run
3. Verify all jobs show ✅ green checkmarks

## Expected Workflows

- 🚀 Required CI (`required-ci`, 12 required jobs)
  - lint · contracts · guardrails · test-monolith · test-microservices
  - frontend-tests · skills-structural · event-stack-live
  - images-plan · images-build · live-e2e-required · runtime-truth-required

- 🧪 Additional workflows
  - `doc-integrity` (including the live documentation contract)
  - runtime truth, architecture, frontend theme, observability, and deployment validation

- Ω Omega Intelligence Pipeline (1 job)
- Universal Repository Synchronization Protocol (1 job)

## Troubleshooting

If any workflow fails:

1. Check the specific job logs
2. Run the failing command locally
3. Fix the issue
4. Commit and push again

## Success Criteria

✅ All workflows complete with green checkmarks
✅ No red X marks on any job
✅ Repository badge shows passing status
