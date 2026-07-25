# syntax=docker/dockerfile:1
# Playwright's own image — it carries the browser binaries and system libraries.
# Keep the tag pinned to the playwright version in requirements.txt; a mismatch
# produces a confusing "browser not found" at runtime.
FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

COPY browser_agent/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY browser_agent ./browser_agent
COPY agents ./agents
COPY backend/app ./app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PLAYWRIGHT_HEADLESS=true \
    PLAYWRIGHT_ARTIFACT_DIR=/app/artifacts

RUN mkdir -p /app/artifacts && chown -R pwuser:pwuser /app

# The most exposed process in the system runs unprivileged. It holds systeme.io
# credentials and drives a real browser; it does not need root.
USER pwuser

CMD ["python", "-m", "browser_agent.agent"]
