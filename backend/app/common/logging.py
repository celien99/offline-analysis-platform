from __future__ import annotations

import structlog

from app.core.config import settings
from app.core.security import generate_trace_id


def configure_logging(*, debug: bool = False) -> None:
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if debug:
        shared_processors.append(structlog.dev.ConsoleRenderer())
    else:
        shared_processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.make_filtering_bound_logger(20 if not debug else 10),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    return structlog.get_logger(name or __name__)


def bind_context(**kwargs: object) -> None:
    structlog.contextvars.bind_contextvars(**kwargs)


def new_trace_context() -> str:
    trace_id = generate_trace_id()
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    return trace_id


def setup_logging() -> None:
    configure_logging(debug=settings.debug)
