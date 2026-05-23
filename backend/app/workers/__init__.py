from __future__ import annotations

import asyncio
import threading
from collections.abc import Coroutine
from typing import TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[None, None, T]) -> T:
    """在同步 Celery task 上下文中运行异步协程。

    处理两种情况：
    1. 当前线程无 event loop（prefork pool 子进程）→ 创建新 loop 运行
    2. 当前线程已有 event loop → 在新线程中创建独立 loop 运行，
       避免 SQLAlchemy async engine 的 Future 被附加到错误的 loop。
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 无运行中的 loop，直接创建新的
        return asyncio.run(coro)

    # 已有运行中的 loop（例如 celery eventlet/gevent pool），
    # 在新线程中运行以避免 event loop 冲突
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
