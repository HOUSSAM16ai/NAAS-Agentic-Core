# D-173 (D-172 gap closure): mirror the proven planning-agent Dockerfile so the
# `from microservices.conversation_service...` absolute imports resolve. The flat
# `COPY . .` + `main:app` broke module resolution; python:3.11 also fails on the
# PEP 695 `type X =` syntax the app uses (3.12-only).
FROM python:3.14-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app:$PYTHONPATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The build context is the service directory; reconstruct the package path so
# `microservices.conversation_service.*` imports resolve (independence pattern).
COPY . /app/microservices/conversation_service

EXPOSE 8010

CMD ["uvicorn", "microservices.conversation_service.main:app", "--host", "0.0.0.0", "--port", "8010"]
