from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    """在同步 Celery task 上下文中运行异步协程。

    Celery prefork 模式下 worker_init 已为每个子进程创建好 event loop 并
    dispose 了继承的 DB 连接池，这里直接复用该 loop，避免连接池归属错误的 loop。
    """
    try:
        # 已有运行中的 loop（如 eventlet/gevent pool），在独立线程中运行
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # prefork 子进程：worker_init 已创建并设置好 loop，直接运行
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)

    # 有运行中 loop 的情况，在新线程中运行避免冲突
    result: T | None = None
    error: Exception | None = None

    def _runner() -> None:
        nonlocal result, error
        try:
            result = asyncio.run(coro)
        except Exception as e:
            error = e

    thread = threading.Thread(target=_runner)
    thread.start()
    thread.join()

    if error is not None:
        raise error
    return result  # type: ignore[return-value]
