FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 先复制依赖描述文件（利用 Docker 层缓存：依赖未变时跳过重装）
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen

# 复制应用代码
COPY backend/app/ ./app/
COPY backend/alembic.ini .
COPY backend/alembic/ ./alembic/
COPY ml/ ./ml/

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
