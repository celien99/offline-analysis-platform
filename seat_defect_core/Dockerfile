FROM python:3.11-slim

# OpenCV 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# 复制源码和默认配置
COPY . .

ENTRYPOINT ["python", "-m", "seat_defect_core"]
CMD ["--help"]
