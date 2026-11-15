FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    HOST=0.0.0.0 \
    PORT=8000 \
    CAREER_GRAPH_DATA=/data

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN apt-get update \
    && apt-get install -y --no-install-recommends libatomic1 \
    && uv sync --frozen --no-dev \
    && .venv/bin/playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH"
VOLUME ["/data"]
EXPOSE 8000
CMD ["career-graph"]
