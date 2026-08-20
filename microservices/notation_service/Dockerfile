# D-185 — notation-service. Build context is the REPO ROOT so the
# `microservices.notation_service.*` package path the app imports actually exists
# inside the image (a service-dir context would flatten it and crash on import).
FROM python:3.14-slim
WORKDIR /app

COPY microservices/notation_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Only the service subtree — it is fully self-contained (vendored registry, no
# monolith import, no shared/ import at runtime).
COPY microservices/__init__.py ./microservices/__init__.py
COPY microservices/notation_service ./microservices/notation_service

EXPOSE 8011
CMD ["uvicorn", "microservices.notation_service.main:app", "--host", "0.0.0.0", "--port", "8011"]
