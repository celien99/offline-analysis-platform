FROM python:3.11-slim

# OpenCV 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 先复制依赖描述文件（利用 Docker 层缓存）
COPY seat_defect_core/pyproject.toml seat_defect_core/uv.lock ./
RUN uv sync --frozen

# 复制源码
COPY seat_defect_core/ ./
COPY ml/ ./ml/

ENV PATH="/app/.venv/bin:$PATH"
ENTRYPOINT ["python", "-m", "seat_defect_core"]
CMD ["--help"]
