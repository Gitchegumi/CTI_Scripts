# ===========================================
# TradeGumi Combined Container
# ===========================================
# Runs both the Python bot (port 8199) and Next.js dashboard (port 3000)

FROM python:3.13-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# ===========================================
# Bot stage
# ===========================================
FROM base AS bot

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

# ===========================================
# Dashboard stage
# ===========================================
FROM node:22-alpine AS dashboard

WORKDIR /app/dashboard

# Copy dashboard source
COPY dashboard/package.json dashboard/package-lock.json* ./

# Install deps
RUN npm install

# Copy dashboard source
COPY dashboard/next.config.js dashboard/tsconfig.json ./
COPY dashboard/src ./src
COPY dashboard/public ./public

# Build
RUN npm run build

# ===========================================
# Final combined image
# ===========================================
FROM base

WORKDIR /app

# Copy from bot stage
COPY --from=bot /app/.venv ./.venv
COPY --from=bot /app/pyproject.toml /app/poetry.toml ./
COPY --from=bot /app/src ./src
COPY --from=bot /app/README.md ./

# Copy from dashboard stage (full directory for npm start)
COPY --from=dashboard /app/dashboard ./dashboard

# Recreate symlink for dashboard data access
RUN mkdir -p /app/src/tradegumi/data /app/dashboard/public && \
    rm -f /app/dashboard/public/data && \
    ln -sf /app/src/tradegumi/data /app/dashboard/public/data

# Environment
ENV PYTHONUNBUFFERED=1
ENV POETRY_VIRTUALENVS_IN_PROJECT=1
ENV PYTHONPATH=/app/src
ENV PATH="/app/.venv/bin:$PATH"
ENV NEXT_PUBLIC_API_URL=http://localhost:8199

# Ports
EXPOSE 8199 3000

# Volume for runtime data
VOLUME ["/app/src/tradegumi/data"]

# Install Node.js in final image (for dashboard npm start)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]