# AGENTS.md

This file provides guidance to Codex agents when working with code in this repository.

## Development Commands

Package manager is **uv** for Python, not pip. Python version: **3.11**.
This repository uses a **uv workspace monorepo** layout. Manage Python dependencies from the repository root.

```bash
# First-time dependency installation
uv sync --all-packages

# Infrastructure
docker compose -f backend/docker-compose.yml up -d

# Backend API
cp backend/.env.example backend/.env
uv run --directory backend alembic upgrade head
uv run --directory backend uvicorn app.main:app --reload --port 8000

# Local Celery worker
uv run --directory backend celery -A app.infrastructure.queue.celery_app worker -l info -c 2

# Backend tests and checks
uv run --directory backend pytest -v
uv run --directory backend pytest app/tests/test_api.py -v
uv run ruff check backend/app
uv run mypy backend/app

# Online detection core
uv run python -m seat_defect_core --help
uv run python -m seat_defect_core \
  --config seat_defect_core/config.example.json \
  --images "cam_front=sample.jpg"

# Frontend
cd frontend
pnpm install
pnpm run dev
pnpm run build

# End-to-end demo
uv run python scripts/demo_full_loop.py \
  --backend http://localhost:8000 --images ./sample_images
```

## Project Overview

This is an industrial AI offline intelligent analysis platform for seat defect detection.
It is an AI evolution platform that works alongside the online real-time detection system: YOLO + PatchCore + Filter Classifier.

The offline platform handles anomaly accumulation, clustering, VLM-based explanation, knowledge base construction, and filter classifier training. It must not participate in online real-time detection.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI async, SQLAlchemy async, Celery, Redis |
| Database | PostgreSQL + pgvector |
| Object Storage | MinIO |
| AI/ML | PyTorch, ResNet18 embeddings, UMAP + HDBSCAN clustering, Qwen2.5-VL/InternVL multimodal |
| Model Registry | MLflow |
| Frontend | React + Ant Design + Plotly |
| Deployment | Docker, Kubernetes |

## Architecture Principles

- Use strict layered architecture: API -> Service -> Domain -> Repository -> Infrastructure.
- API routers must not access databases directly. Routers handle parameters, response formatting, and dependency injection.
- Organize modules by business domain, such as `anomaly/`, `cluster/`, `embedding/`, `review/`, `training/`, `multimodal/`, and `registry/`.
- Use async everywhere in the backend: FastAPI endpoints, SQLAlchemy, Redis, and MinIO.
- CPU/GPU-heavy work such as embedding extraction, clustering, VLM analysis, and training must run in Celery workers.
- Keep AI inference logic decoupled from business logic. Models do inference; services handle business workflows.
- Prefer unified AI interfaces such as `EmbeddingExtractor` and `VLMAnalyzer` protocols so models remain swappable.

## Code Standards

- Add `from __future__ import annotations` in Python files.
- Use full type annotations and keep code mypy-compatible. Avoid unnecessary `Any`.
- Use Pydantic Settings for configuration. Do not hardcode environment constants.
- Use structured logging through `structlog` with context such as `trace_id`, `cluster_id`, `anomaly_id`, `model_version`, and `camera_id`.
- Use Alembic for database migrations.
- Use repository classes for database access. Do not put raw SQLAlchemy queries in business services unless there is already a clear local pattern.
- Use custom exceptions with error codes. Never use bare `except: pass`.
- Keep functions focused and small. Avoid giant service classes and dumping-ground utility modules.
- Avoid circular dependencies.
- 核心逻辑需要中文注释，说明业务意图和关键边界条件。
- 新功能必须处理边界情况，不要假设用户输入永远合法。

## Key Implementation Patterns

**Soft delete:** `BaseModel` in `backend/app/models/base.py` provides `id`, `created_at`, `updated_at`, `deleted_at`, and `trace_id`. Repository queries should filter `deleted_at.is_(None)`. Use `BaseRepository.soft_delete()` instead of hard deletes.

**Exception hierarchy:** Custom exceptions inherit from `AppError(code, message)` in `backend/app/core/exceptions.py`. The FastAPI app has a global `AppError` handler that returns `ErrorResponse`.

**Repository pattern:** Repositories inherit from `BaseRepository[T]` in `backend/app/repositories/base.py`. Services receive an `AsyncSession` and instantiate repositories internally.

**Dependency injection:** `backend/app/api/deps.py` provides `get_session()` and `get_minio()`. Routers should use `Depends(get_session)` and `Depends(get_minio)`.

**Domain entities are not ORM models:** Domain entities live under `backend/app/domain/*/entities.py`. Repositories map between ORM models and domain entities.

**Structured logging:** Use `get_logger(__name__)` from `app.common.logging`. Bind request or workflow context with `structlog.contextvars.bind_contextvars(...)` or `new_trace_context()`. Log event names should use `snake_case`.

**Type aliases:** Shared aliases live in `backend/app/common/types.py`, including `AnomalyId`, `ClusterId`, `EmbeddingId`, `CameraId`, `ModelVersionId`, `EmbeddingArray`, `ImageData`, and `JsonDict`.

## Project Structure

```text
pyproject.toml
uv.lock

backend/
  app/
    api/
    domain/
    infrastructure/
    repositories/
    services/
    workers/
    schemas/
    models/
    core/
    common/
    tests/
  scripts/
  pyproject.toml

defect_protocol/
  defect_protocol/
  tests/
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
  alignment/
  pyproject.toml

seat_defect_core/
  pyproject.toml
```

## Implementation Order

1. Design module boundaries and interfaces.
2. Define schemas and domain models.
3. Implement repositories.
4. Implement services.
5. Implement API routers last.

## Codex Workflow

- Act directly when the user gives a clear implementation request.
- Prefer small, atomic commits after each independent feature, fix, or cleanup.
- Use Conventional Commits, such as `feat:`, `fix:`, `refactor:`, and `docs:`.
- Before committing, run the necessary formatting, type checks, or focused tests for the changed area when practical.
- Do not mix unrelated changes in one commit.
- Ask before destructive operations such as `git reset --hard`, broad file deletion, or commands that may damage the environment.
- When changing architecture, restructuring files, or refactoring user-facing workflows, update relevant README or project documentation in the same work session.
- Preserve user changes in the working tree. Do not revert files you did not intentionally modify unless the user explicitly asks.
