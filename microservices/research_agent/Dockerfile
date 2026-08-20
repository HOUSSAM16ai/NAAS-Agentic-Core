# Research Agent Dockerfile
FROM python:3.14-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app"

# Install basics
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt .
# Install specific heavy dependencies if needed separately or rely on main requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy Code (Constructing package structure from service context)
COPY . /app/microservices/research_agent

# Run
CMD ["uvicorn", "microservices.research_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
