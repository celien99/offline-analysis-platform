"""Celery Worker 子进程初始化：处理 prefork 后的 event loop 和 DB pool 重建。

prefork 模式下子进程继承父进程的 async engine，
但连接池中的连接属于父进程的 event loop，导致 "got Future attached to a different loop"。
"""

from __future__ import annotations

import asyncio
import logging

from celery import signals

logger = logging.getLogger(__name__)


@signals.worker_process_init.connect
def _on_worker_process_init(**kwargs: object) -> None:
    """每个 worker 子进程启动时：创建新 event loop 并销毁继承的 DB 连接池。"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _dispose() -> None:
        from app.infrastructure.database.session import engine
        await engine.dispose()

    loop.run_until_complete(_dispose())
    logger.info("Worker process initialized: event loop created, engine pool disposed")
