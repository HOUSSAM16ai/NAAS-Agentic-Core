# content-retrieval-skill. Rewritten in D-205 for the same reason as
# foundations-service: the first CI build of this image proved the container
# could never start — a flat `COPY . .` + `CMD uvicorn main:app` against a
# main.py that imports `microservices.content_retrieval_skill.*` absolutely.
# Never caught because this service is in no compose file and was never built.
#
# The pattern below is notation-service's, which is proven.
FROM python:3.14-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app:$PYTHONPATH"

COPY microservices/content_retrieval_skill/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY microservices/__init__.py ./microservices/__init__.py
COPY microservices/content_retrieval_skill ./microservices/content_retrieval_skill

# main.py reads KB_ROOT, defaulting to a Codespaces-only absolute path
# (/workspaces/...) that does not exist in an image. Point it at the corpus this
# image actually carries, and ship the corpus.
COPY knowledge_base ./knowledge_base
ENV KB_ROOT=/app/knowledge_base

EXPOSE 8009
CMD ["uvicorn", "microservices.content_retrieval_skill.main:app", "--host", "0.0.0.0", "--port", "8009"]
