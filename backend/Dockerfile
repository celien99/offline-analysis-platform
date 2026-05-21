FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY backend/pyproject.toml .
RUN uv pip install --system --no-cache \
    fastapi>=0.115.0 \
    uvicorn[standard]>=0.30.0 \
    sqlalchemy[asyncio]>=2.0.30 \
    asyncpg>=0.29.0 \
    pgvector>=0.3.0 \
    alembic>=1.13.0 \
    pydantic>=2.7.0 \
    pydantic-settings>=2.3.0 \
    celery[redis]>=5.4.0 \
    redis>=5.0.0 \
    minio>=7.2.0 \
    structlog>=24.4.0 \
    httpx>=0.27.0 \
    python-multipart>=0.0.9 \
    numpy>=1.26.0

COPY backend/app/ ./app/
COPY backend/alembic.ini .
COPY backend/alembic/ ./alembic/
COPY ml/ ./ml/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
