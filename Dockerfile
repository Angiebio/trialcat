# trialcat — production container
# Single-stage build for simplicity. Multi-stage optimization can wait until
# we have enough dependencies to care about image size. Right now we optimize
# for "I can read and understand this file in 30 seconds."

FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Environment tuning:
# - PYTHONDONTWRITEBYTECODE: no .pyc files cluttering the image
# - PYTHONUNBUFFERED: logs flush immediately (critical for Docker log visibility)
# - PIP_NO_CACHE_DIR: smaller image, we're not reinstalling anything
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend

# Install system dependencies we'll need eventually:
# - curl for Fly.io health checks and debugging
# - No build tools yet — if a dependency ever needs compilation we'll add gcc
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first so Docker layer caching helps us:
# code changes won't force a full pip reinstall.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/backend/requirements.txt

# Copy the rest of the app
COPY backend /app/backend
COPY frontend /app/frontend
COPY .env.example /app/.env.example

# Create the data directory (SQLite will live here)
RUN mkdir -p /app/data

# Expose the port the app runs on
EXPOSE 8000

# Healthcheck — lets Docker and Fly.io know if the container is alive.
# Hitting /health is cheap (no DB calls) so this is safe every 30s.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run uvicorn from the backend directory so imports resolve correctly.
# --host 0.0.0.0 so the container is reachable from outside.
# Not using --reload in the image (dev compose file overrides this).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--app-dir", "/app/backend"]
