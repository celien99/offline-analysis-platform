from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    """Run an async coroutine from synchronous Celery task context."""
    return asyncio.run(coro)
