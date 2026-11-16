# Stage 1: build the React UI into src/career_buddy/web/static (vite's outDir is ../src/career_buddy/web/static).
FROM node:22-alpine AS ui
RUN corepack enable && corepack prepare pnpm@12.16.1 --activate
WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# Stage 2: the app. The API serves the built UI at / and the API at /api.
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HOST=0.0.0.0 \
    PORT=8000 \
    CAREER_BUDDY_DATA=/data \
    CAREER_BUDDY_KEY_STORE=file \
    CAREER_BUDDY_NO_BROWSER=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
COPY --from=ui /app/src/career_buddy/web/static ./src/career_buddy/web/static
RUN apt-get update \
    && apt-get install -y --no-install-recommends libatomic1 \
    && uv sync --frozen --no-dev \
    && .venv/bin/playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH"
VOLUME ["/data"]
EXPOSE 8000
CMD ["career-buddy"]
