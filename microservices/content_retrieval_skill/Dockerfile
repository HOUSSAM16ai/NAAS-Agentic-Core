# Dockerfile for content_retrieval_skill
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/microservices/content_retrieval_skill

ENV PYTHONPATH=/app
ENV PORT=8009

CMD ["uvicorn", "microservices.content_retrieval_skill.main:app", "--host", "0.0.0.0", "--port", "8009"]
