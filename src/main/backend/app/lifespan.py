from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from backend.app.auth.auth import validate_auth_configuration
from backend.app.config import (
    bool_env,
    db_keepwarm_interval_seconds,
    db_prewarm_connection_count,
    startup_db_disabled,
)
from backend.app.db.db import check_db_connection, init_db, warm_db_pool
from backend.app.services import coordination
from backend.app.services.realtime import start_runtime as start_realtime_runtime
from backend.app.services.realtime import stop_runtime as stop_realtime_runtime


async def db_keepwarm_loop(interval_seconds: int) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        await asyncio.to_thread(check_db_connection)


async def keepalive_loop() -> None:
    while True:
        await asyncio.sleep(3600)


async def cancel_task(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_auth_configuration()
    coordination.validate_configuration()

    keepalive_task = None
    db_keepwarm_task = None
    try:
        await start_realtime_runtime()
        if bool_env("SIPM_KEEPALIVE_TASK", False):
            keepalive_task = asyncio.create_task(keepalive_loop())

        if not startup_db_disabled():
            init_db()
            prewarm_connection_count = db_prewarm_connection_count()
            if prewarm_connection_count:
                warm_db_pool(connection_count=prewarm_connection_count)
            keepwarm_interval_seconds = db_keepwarm_interval_seconds()
            if keepwarm_interval_seconds:
                if not prewarm_connection_count:
                    check_db_connection()
                db_keepwarm_task = asyncio.create_task(db_keepwarm_loop(keepwarm_interval_seconds))
        yield
    finally:
        await stop_realtime_runtime()
        await cancel_task(db_keepwarm_task)
        await cancel_task(keepalive_task)
