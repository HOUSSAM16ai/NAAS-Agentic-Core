# Transition Service Dockerfile — منظومة وكلاء تحول الذكاء الاصطناعي (D-240).
#
# نمطُ النسخ أدناه مأخوذٌ من `notation-service`/`foundations-service` المُثبتَين:
# سياقُ البناء هو جذر المستودع (المصفوفة `context: .`)، والمساراتُ المطلقة
# `microservices.transition_service.*` تتطلّب أن يعيشَ الشجر في
# `/app/microservices/transition_service` مع `__init__.py` لأبيه — وإلا
# `ModuleNotFoundError: No module named 'microservices.transition_service'`
# (نفس العطب الذي ماتت عليه foundations-service في D-183).

FROM python:3.12-slim AS builder
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    && rm -rf /var/lib/apt/lists/*
COPY microservices/transition_service/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app:$PYTHONPATH"
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
# شجرة الخدمة داخل حزمة microservices — بلا استيراد لـ `app` أو `shared` (حدود الخدمات).
COPY microservices/__init__.py ./microservices/__init__.py
COPY microservices/transition_service ./microservices/transition_service
# مستخدمٌ غير جذري.
RUN useradd -m -u 1000 agentuser && \
    chown -R agentuser:agentuser /app
USER agentuser
EXPOSE 8012
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8012/health || exit 1
CMD ["uvicorn", "microservices.transition_service.src.main:app", "--host", "0.0.0.0", "--port", "8012"]
