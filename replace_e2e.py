import re

with open('.github/workflows/live-e2e.yml', 'r') as f:
    content = f.read()

# Add new environment variables to live-e2e.yml
env_vars = """      HONCHO_API_KEY: ${{ secrets.HONCHO_API_KEY }}
      ENVIRONMENT: development
      LLM_MOCK_MODE: "0"
      REQUIRE_ORCHESTRATOR: "0"
      ORCHESTRATOR_LOCAL_FALLBACK_ENABLED: "1"
      USER_SERVICE_URL: "http://127.0.0.1:8000"
      ORCHESTRATOR_SERVICE_URL: "http://127.0.0.1:9999"
      OPENROUTER_EXTRA_MODELS: "google/gemini-2.5-flash"
      E2E_BACKEND: http://127.0.0.1:8000"""

content = re.sub(
    r'      HONCHO_API_KEY: \$\{\{ secrets\.HONCHO_API_KEY \}\}\n      ENVIRONMENT: development\n      LLM_MOCK_MODE: "0"\n      REQUIRE_ORCHESTRATOR: "0"\n      E2E_BACKEND: http://127\.0\.0\.1:8000',
    env_vars,
    content
)

with open('.github/workflows/live-e2e.yml', 'w') as f:
    f.write(content)
