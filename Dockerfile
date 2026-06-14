# ===========================================
# TradeGumi multi-service image
# ===========================================
# This Dockerfile produces TWO independent images via named build targets:
#   --target python     → tradegumi-worker and tradegumi-api (Python; they
#                          differ only by which entrypoint docker-compose runs)
#   --target dashboard  → tradegumi-dashboard (Next.js on Node)
#
# The worker/API and the dashboard no longer share a process or an image — a
# failure in one cannot take down the others (see specs/019-split-runtime-containers).

# ── Python base (shared by worker + api) ──────────────────────
FROM python:3.13-slim AS python-base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# ===========================================
# Python application image (worker + api)
# ===========================================
FROM python-base AS python

WORKDIR /app

# Copy source structure to match expected layout
COPY src/pyproject.toml src/poetry.toml ./
COPY src/tradegumi ./src/tradegumi
COPY src/trading_scripts ./src/trading_scripts

# Create the data directory
RUN mkdir -p /app/src/tradegumi/data

# Install dependencies (poetry creates .venv in-project due to poetry.toml)
RUN poetry install --no-interaction --no-ansi --no-root

# Copy remaining source docs
COPY src/README.md ./

# Environment
ENV PYTHONUNBUFFERED=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=1
ENV PYTHONPATH=/app/src
ENV PATH="/app/.venv/bin:$PATH"

# Only the API service publishes this port; the worker has no public port.
EXPOSE 8199

# Volume for runtime data
VOLUME ["/app/src/tradegumi/data"]

# Per-service entrypoints. docker-compose selects which one each service runs;
# the image defaults to the worker.
COPY entrypoint.worker.sh entrypoint.api.sh /
RUN chmod +x /entrypoint.worker.sh /entrypoint.api.sh

ENTRYPOINT ["/entrypoint.worker.sh"]

# ===========================================
# Dashboard build stage
# ===========================================
FROM node:22-alpine AS dashboard-build

WORKDIR /app/dashboard

# Install deps from the lockfile for reproducible dashboard builds
COPY dashboard/package.json dashboard/package-lock.json* ./
RUN npm ci

# Copy dashboard source
COPY dashboard/next.config.js dashboard/tsconfig.json dashboard/postcss.config.mjs ./
COPY dashboard/src ./src
COPY dashboard/public ./public

# Accept build-time API URL (must be declared before npm run build)
ARG NEXT_PUBLIC_API_URL=http://10.0.0.116:8199
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

# Build
RUN npm run build

# ===========================================
# Dashboard runtime image
# ===========================================
FROM node:22-alpine AS dashboard

WORKDIR /app/dashboard
ENV NODE_ENV=production

# Copy the built dashboard (includes .next, node_modules, public, config)
COPY --from=dashboard-build /app/dashboard ./

EXPOSE 3000

CMD ["npm", "start"]
