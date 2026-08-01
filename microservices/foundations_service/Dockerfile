# D-183 — foundations-service. Rewritten in D-205 after the new `images-build`
# gate built this image for the first time and it died on startup:
#
#   File "/app/main.py", line 32, in <module>
#     from microservices.foundations_service.prom_metrics import (
#   ModuleNotFoundError: No module named 'microservices'
#
# The old file was a flat `COPY . .` + `CMD uvicorn main:app`, while main.py uses
# absolute `microservices.foundations_service.*` imports — so the container could
# never have started. It went unnoticed because this service appears in no compose
# file and nothing ever built it. D-173 already fixed exactly this for
# conversation-service; this copy just never got the fix.
#
# The pattern below is notation-service's, which is proven.
FROM python:3.12-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app:$PYTHONPATH"

COPY microservices/foundations_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Only the service subtree — the engines are vendored; no `app` or `shared` import.
COPY microservices/__init__.py ./microservices/__init__.py
COPY microservices/foundations_service ./microservices/foundations_service

EXPOSE 8010
CMD ["uvicorn", "microservices.foundations_service.main:app", "--host", "0.0.0.0", "--port", "8010"]
