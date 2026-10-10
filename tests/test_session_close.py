import asyncio
import unittest
from unittest.mock import AsyncMock

from flet_android_background import BackgroundTask


class SessionCloseTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_close_cancels_work_without_a_client_rpc(self):
        service = AsyncMock()
        service.stop_foreground_service.side_effect = RuntimeError("destroyed session")
        task = BackgroundTask(service)
        cleanup = AsyncMock()
        await task.start(asyncio.Event().wait, on_stop=cleanup)
        await asyncio.wait_for(task.on_session_close(), .5)
        self.assertFalse(task.running)
        cleanup.assert_awaited_once()
        service.stop_foreground_service.assert_not_awaited()
        self.assertIsNone(task.error)
        await task.on_session_close()
        cleanup.assert_awaited_once()
        with self.assertRaisesRegex(RuntimeError, "create a new BackgroundTask"):
            await task.start(AsyncMock())
        service.start_foreground_service.assert_awaited_once()

    async def test_close_during_start_never_launches_work(self):
        entered, release = asyncio.Event(), asyncio.Event()
        service = AsyncMock()

        async def start(**kwargs):
            entered.set()
            await release.wait()

        service.start_foreground_service.side_effect = start
        task = BackgroundTask(service)
        work = AsyncMock()
        starting = asyncio.create_task(task.start(work))
        await entered.wait()
        closing = asyncio.create_task(task.on_session_close())
        await asyncio.sleep(0)
        release.set()
        with self.assertRaisesRegex(RuntimeError, "session closed"):
            await starting
        await closing
        work.assert_not_awaited()
        service.stop_foreground_service.assert_not_awaited()

    async def test_cleanup_failure_after_close_is_recorded_without_rpc(self):
        service = AsyncMock()
        task = BackgroundTask(service)
        await task.start(asyncio.Event().wait, on_stop=AsyncMock(side_effect=ValueError("cleanup")))
        await task.on_session_close()
        self.assertFalse(task.running)
        self.assertIsInstance(task.error, ValueError)
        service.stop_foreground_service.assert_not_awaited()
