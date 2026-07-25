# syntax=docker/dockerfile:1
# Agent worker image. Build from the repository root — a worker needs `agents/`,
# `vector_memory/`, and the backend's `app` package for the ORM and schemas:
#   docker build -f agents/Dockerfile .
FROM python:3.11-slim AS builder

WORKDIR /build
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim AS runtime

RUN useradd --create-home --uid 10001 aibo
WORKDIR /app

COPY --from=builder /install /usr/local
COPY backend/app ./app
COPY agents ./agents
COPY vector_memory ./vector_memory

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

USER aibo

# Overridden per agent in compose and in the Kubernetes deployments.
CMD ["python", "-m", "agents.worker", "--agent", "research_agent"]
