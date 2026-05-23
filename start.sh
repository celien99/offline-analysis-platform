#!/bin/bash
# 工业座椅缺陷检测离线分析平台 — 一键启动脚本
#
# 用法:
#   ./start.sh              # 启动所有服务
#   ./start.sh --no-frontend # 不启动前端
#   ./start.sh --stop       # 停止所有服务
#   ./start.sh --status     # 查看服务状态

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${CYAN}[STEP]${NC}  $1"; }

# ---- 命令行参数 ----
NO_FRONTEND=false
ACTION="start"

for arg in "$@"; do
    case $arg in
        --no-frontend) NO_FRONTEND=true ;;
        --stop) ACTION="stop" ;;
        --status) ACTION="status" ;;
        --help|-h) echo "用法: $0 [--no-frontend] [--stop] [--status]"; exit 0 ;;
    esac
done

# ---- 停止服务 ----
if [ "$ACTION" = "stop" ]; then
    log_info "停止所有 Docker 服务..."
    docker compose -f backend/docker-compose.yml down
    log_info "已停止全部服务"
    exit 0
fi

# ---- 查看状态 ----
if [ "$ACTION" = "status" ]; then
    echo "=== Docker 服务 ==="
    docker compose -f backend/docker-compose.yml ps 2>/dev/null || echo "  无运行中的服务"
    echo ""
    echo "=== 端口监听 ==="
    lsof -i :8000 -sTCP:LISTEN 2>/dev/null && echo "  :8000 (API) 已占用" || echo "  :8000 (API) 空闲"
    lsof -i :3000 -sTCP:LISTEN 2>/dev/null && echo "  :3000 (前端) 已占用" || echo "  :3000 (前端) 空闲"
    exit 0
fi

# ---- 前置检查 ----
echo ""
echo "================================================"
echo "  工业座椅缺陷检测离线分析平台"
echo "  Industrial AI Offline Analysis Platform"
echo "================================================"
echo ""

# 1. Docker
log_step "检查 Docker..."
if ! docker info &>/dev/null; then
    log_error "Docker 未运行，请先启动 Docker Desktop"
    exit 1
fi
log_info "Docker 已运行"

# 2. Python
log_step "检查 Python..."
PYTHON_BIN=""
if [ -f backend/.venv/bin/python ]; then
    PYTHON_BIN="backend/.venv/bin/python"
    log_info "使用 backend/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
    log_warn "未找到 backend/.venv，使用系统 python3"
else
    log_error "Python 3.11+ 未安装"
    exit 1
fi

# 3. 依赖检查
log_step "检查依赖安装..."
if [ ! -f backend/.venv/bin/python ]; then
    log_warn "后端 .venv 不存在，正在安装..."
    (cd backend && uv sync) || { log_error "后端依赖安装失败"; exit 1; }
fi
if [ ! -f seat_defect_core/.venv/bin/python ]; then
    log_warn "seat_defect_core .venv 不存在，正在安装..."
    (cd seat_defect_core && uv sync) || log_warn "seat_defect_core 依赖安装失败（可稍后手动安装）"
fi

# ---- 启动 Docker 基础设施 ----
# 本地开发模式：API 跑在本地，Docker 只跑基础设施
# 生产/全 Docker 模式：docker compose up -d（不加服务列表，含 API）
log_step "启动 Docker 基础设施..."
docker compose -f backend/docker-compose.yml up -d \
    db redis minio minio-init mlflow

# 等待就绪
log_info "等待 PostgreSQL 就绪..."
until docker compose -f backend/docker-compose.yml exec -T db pg_isready -U postgres &>/dev/null; do
    sleep 1
done
log_info "PostgreSQL 就绪"

log_info "等待 Redis 就绪..."
until docker compose -f backend/docker-compose.yml exec -T redis redis-cli ping &>/dev/null; do
    sleep 1
done
log_info "Redis 就绪"

# ---- 数据库迁移 ----
log_step "运行数据库迁移..."
(cd backend && .venv/bin/python -m alembic upgrade head) || log_warn "数据库迁移失败（可能已是最新）"

# ---- 启动后端 API ----
# 先停掉可能已在 Docker 中运行的 API 容器（避免端口 8000 冲突）
if docker compose -f backend/docker-compose.yml ps api --status running 2>/dev/null | grep -q "api-1"; then
    log_info "停掉 Docker api 容器（本地开发用本地 uvicorn）..."
    docker compose -f backend/docker-compose.yml stop api
fi

log_step "启动后端 API (port 8000)..."
(cd backend && .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000) &
API_PID=$!
sleep 2

if kill -0 $API_PID 2>/dev/null; then
    log_info "后端 API 已启动: http://localhost:8000"
    log_info "  Swagger 文档: http://localhost:8000/docs"
    log_info "  健康检查:    http://localhost:8000/health"
else
    log_error "后端 API 启动失败，请检查日志"
    exit 1
fi

# ---- 启动 Celery Worker ----
log_step "启动 Celery Worker（本地开发模式）..."
(cd backend && .venv/bin/celery -A app.infrastructure.queue.celery_app worker -l info -c 2) &
WORKER_PID=$!
sleep 2

if kill -0 $WORKER_PID 2>/dev/null; then
    log_info "Celery Worker 已启动"
else
    log_error "Celery Worker 启动失败，请检查日志"
    exit 1
fi

# ---- 启动前端 ----
if [ "$NO_FRONTEND" = false ]; then
    if [ -f frontend/node_modules/.package-lock.json ] || [ -d frontend/node_modules ]; then
        log_step "启动前端 (port 3000)..."
        (cd frontend && pnpm run dev) &
        FRONTEND_PID=$!
        sleep 2
        if kill -0 $FRONTEND_PID 2>/dev/null; then
            log_info "前端已启动: http://localhost:3000"
        else
            log_warn "前端启动失败，可通过 ./start.sh --no-frontend 跳过"
        fi
    else
        log_warn "前端依赖未安装，跳过。运行: cd frontend && pnpm install"
    fi
fi

# ---- 总结 ----
echo ""
echo "================================================"
echo "  启动完成!"
echo "================================================"
echo ""
echo "  后端 API:     http://localhost:8000"
echo "  API 文档:     http://localhost:8000/docs"
if [ "$NO_FRONTEND" = false ] && kill -0 $FRONTEND_PID 2>/dev/null; then
    echo "  前端:         http://localhost:3000"
fi
echo "  MinIO 控制台: http://localhost:9001 (minioadmin/minioadmin)"
echo "  MLflow:       http://localhost:5001"
echo ""
echo "  在线检测命令:"
echo "    ./seat_defect_core/.venv/bin/python -m seat_defect_core \\"
echo "      --config seat_defect_core/config.example.json \\"
echo "      --images \"cam_front=sample.jpg\""
echo ""
echo "  停止服务: ./start.sh --stop"
echo ""

# 等待后台进程（Ctrl+C 时优雅退出）
trap "log_info '正在关闭...'; kill $API_PID $WORKER_PID ${FRONTEND_PID:-} 2>/dev/null; docker compose -f backend/docker-compose.yml stop; exit 0" INT TERM
wait
