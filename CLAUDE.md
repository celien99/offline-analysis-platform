# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

Package manager is **uv** for Python (not pip). Python version: **3.11**.
The repo is a uv workspace — run `uv sync` from root to install all members.

```bash
# Workspace (from repo root)
uv sync                                          # sync all workspace members

# Backend
cd backend
uv sync                                          # install all deps + create .venv
uv run uvicorn app.main:app --reload --port 8000  # dev server (http://localhost:8000)
uv run celery -A app.infrastructure.queue.celery_app worker -l info -c 2  # worker
uv run alembic upgrade head                       # run migrations
uv run pytest -v                                  # all 26 tests
uv run pytest app/tests/test_api.py -v            # single test file
uv run ruff check app                             # lint
uv run mypy app                                   # type check (mypy strict)

# seat_defect_core (online detection core)
cd seat_defect_core
uv sync                                          # install deps (torch, cv2, ultralytics, etc.)
# 设置 PYTHONPATH 指向仓库根目录（避免 types/ 与 stdlib 冲突）
PYTHONPATH=/path/to/repo uv run python -m seat_defect_core --help
PYTHONPATH=/path/to/repo uv run python -m seat_defect_core --config config.example.json --images cam1=img.jpg

# Demo (from repo root)
cd backend && docker compose up -d               # start backend services
uv run --directory ../seat_defect_core python ../scripts/generate_sample_images.py
PYTHONPATH=. uv run --directory seat_defect_core python scripts/demo_full_loop.py

# Frontend
cd frontend
npm install && npm run dev                        # dev server on port 3000 (proxies /api → :8000)
npm run build                                     # typecheck + build
```

## Project Overview

Industrial AI offline intelligent analysis platform for seat defect detection. An "AI evolution platform" that sits alongside an online real-time detection system (YOLO + PatchCore + Filter Classifier). This offline system handles anomaly accumulation, clustering, VLM-based explanation, knowledge base construction, and filter classifier training — but never participates in online real-time detection.

Full architecture spec is in `prompt.md`.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (async), SQLAlchemy (async), Celery, Redis |
| Database | PostgreSQL + pgvector (embedding similarity search) |
| Object Storage | MinIO |
| AI/ML | PyTorch, ResNet18 (embedding), UMAP + HDBSCAN (clustering), Qwen2.5-VL/InternVL (multimodal) |
| Model Registry | MLflow |
| Frontend | React + Ant Design + Plotly |
| Deployment | Docker, Kubernetes |

## Architecture Principles

- **Strict layered architecture**: API → Service → Domain → Repository → Infrastructure. API routers must NOT access databases directly — only parameter handling, response formatting, and dependency injection.
- **Domain-driven module organization**: Split by business domain (`anomaly/`, `cluster/`, `embedding/`, `review/`, `training/`, `multimodal/`, `registry/`), not by technical layer (`routers/`, `services/`, `utils/`).
- **Async everywhere**: FastAPI async endpoints, async SQLAlchemy, async Redis, async MinIO. CPU/GPU-heavy tasks (embedding extraction, clustering, VLM analysis, training) must run in Celery workers, never block the API thread.
- **AI logic decoupled from business logic**: Models do inference only. Services handle business logic. Unified interfaces for all AI models (`EmbeddingExtractor`, `VLMAnalyzer` protocols) to keep models swappable.

## Code Standards (Mandatory)

- `from __future__ import annotations` everywhere; full type annotations; mypy-compatible; no `Any` abuse.
- Pydantic Settings for all configuration — no hardcoded constants (`DB_HOST = "localhost"` forbidden).
- Structured logging via `structlog` with `trace_id`, `cluster_id`, `anomaly_id`, `model_version`, `camera_id`.
- Alembic for DB migrations; Repository pattern for all DB access — no bare `session.query(...)` in business code.
- Custom exceptions with error codes; never bare `except: pass`.
- Functions < 50 lines; classes < 300 lines; no giant Service classes.
- No `utils.py` dumping grounds; no circular dependencies.

## Key Implementation Patterns

These conventions are enforced in the existing code and must be followed for any new code.

**Soft-delete on every table.** `BaseModel` (`backend/app/models/base.py:12`) provides `id` (UUID hex string), `created_at`, `updated_at`, `deleted_at`, and `trace_id`. All repository queries filter on `deleted_at.is_(None)` — never hard-delete rows. `BaseRepository.soft_delete()` sets `deleted_at = now()`.

**Exception hierarchy.** All custom exceptions inherit from `AppError(code, message)` in `backend/app/core/exceptions.py`. Subclasses: `NotFoundError`, `ConflictError`, `ValidationError`, `StorageError`, `EmbeddingGenerationError`, `ClusteringError`, `VLMAnalysisError`, `TrainingError`, `DeploymentError`, `ModelNotFoundError`. The FastAPI app has a global `@app.exception_handler(AppError)` that returns `ErrorResponse`. Routers also use plain `HTTPException` for 404s.

**Repository pattern — all DB access.** Every repository inherits from `BaseRepository[T]` (`backend/app/repositories/base.py`), which provides `get_by_id`, `list_all`, `count`, `create`, `create_all`, `update`, `soft_delete`. Domain-specific repositories add custom queries (e.g., `AnomalyRepository.get_unprocessed`). Services receive an `AsyncSession` and instantiate repositories internally — never call `session.query()` directly.

**Dependency injection.** `backend/app/api/deps.py` provides `get_session()` (async generator yielding `AsyncSession`) and `get_minio()` (returns singleton `MinIOClient`). Routers use `Depends(get_session)` and `Depends(get_minio)`.

**Domain entities ≠ ORM models.** Files in `domain/*/entities.py` define dataclass-style domain objects (not SQLAlchemy models). Services use domain entities for logic; repositories map between ORM models and domain entities. The `domain/*/__init__.py` files re-export the public API.

**Structured logging.** Use `get_logger(__name__)` from `app.common.logging`. Bind context with `structlog.contextvars.bind_contextvars(trace_id=..., anomaly_id=...)` or use the `new_trace_context()` helper. Log messages use `snake_case` event names (e.g., `logger.info("clustering_complete", ...)`).

**Type aliases.** Shared type aliases live in `backend/app/common/types.py`: `AnomalyId`, `ClusterId`, `EmbeddingId`, `CameraId`, `ModelVersionId`, `EmbeddingArray`, `ImageData`, `JsonDict`.

## Project Structure (Target)

```
backend/
  app/
    api/           # FastAPI routers by domain (anomaly/, cluster/, review/, training/, registry/)
    domain/        # Domain models (anomaly/, embedding/, clustering/, multimodal/, training/, registry/)
    infrastructure/# database/, storage/, vector_db/, queue/, logger/, config/
    repositories/  # DB access by domain (anomaly/, embedding/, cluster/, review/)
    services/      # Business logic (embedding/, clustering/, multimodal/, training/, deployment/)
    workers/       # Celery workers (embedding_worker/, clustering_worker/, vlm_worker/, training_worker/)
    schemas/       # Pydantic request/response schemas
    models/        # SQLAlchemy ORM models
    core/          # Config, exceptions, security
    common/        # Shared utilities
    tests/
  scripts/
  docker/
  deployment/
  pyproject.toml

frontend/
  pages/
  components/
  cluster-review/
  anomaly-browser/

ml/
  embedding/
  classifier/
  clustering/
  vlm/
```

## Implementation Order

When building this system, follow this order:
1. Design module boundaries and interfaces first
2. Define schemas and domain models
3. Implement repositories
4. Implement services
5. Implement API routers last

# Claude Code 行为规范

## 1. Git 工作流指令 (核心要求)
* **原子化提交：** 每当你完成一个独立的功能新增、Bug修复或代码完善后，**必须**主动帮我执行 `git commit`，不要等我提醒。
* **Commit 格式：** 严格使用 Conventional Commits 规范（如 `feat:`, `fix:`, `refactor:`, `docs:`）。
* **提交前检查：** 在 commit 之前，先运行必要的代码格式化或基础测试（如果有）。
* **避免大杂烩：** 不要把多个不相关的修改混在同一个 commit 里。

## 2. 代码编写规范
* **注释要求：** 核心逻辑必须用中文写清楚注释。
* **语言偏好：** 优先使用 [写下你的技术栈，例如：TypeScript / Python 3.10+]，避免使用废弃的 API。
* **错误处理：** 添加新功能时，必须包含边界情况（Edge cases）的异常捕获，不要假设用户的输入永远合法。

## 3. 交互偏好
* **直接行动：** 当我提出明确的修改要求时，直接修改代码，不要长篇大论地解释理论，少废话多写代码。
* **确认破坏性操作：** 在执行 `git reset --hard`、删除大量文件或执行可能破坏环境的终端命令前，必须先询问我。