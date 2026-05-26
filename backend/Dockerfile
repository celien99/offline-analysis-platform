FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy workspace dependency manifests (layer caching)
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml ./backend/
COPY ml/pyproject.toml ./ml/
COPY defect_protocol/pyproject.toml ./defect_protocol/

# Install dependencies (cached unless pyproject.toml/uv.lock changes)
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-workspace

# Copy source code
COPY backend/app/ ./backend/app/
COPY backend/alembic.ini ./backend/
COPY backend/alembic/ ./backend/alembic/
COPY ml/ ./ml/
COPY defect_protocol/ ./defect_protocol/

# Install workspace members as editable
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
