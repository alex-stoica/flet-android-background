import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from flet_android_background import BackgroundTask


class BackgroundTaskTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = AsyncMock()
        self.service._owner = 'current'
        self.runner = BackgroundTask(self.service)

    async def test_concurrent_start_and_stop(self):
        cleanup = AsyncMock()
        work = asyncio.Event().wait
        results = await asyncio.gather(*(
            self.runner.start(work, on_stop=cleanup) for _ in range(8)
        ))
        self.assertEqual(results.count(True), 1)
        await asyncio.gather(*(self.runner.stop() for _ in range(8)))
        cleanup.assert_awaited_once()
        self.service.start_foreground_service.assert_awaited_once()
        self.service.stop_foreground_service.assert_awaited_once()
        self.assertFalse(self.runner.running)

    async def test_completion_cleans_up(self):
        cleanup = AsyncMock()
        await self.runner.start(AsyncMock(), on_stop=cleanup)
        await self.runner._task
        cleanup.assert_awaited_once()
        self.service.stop_foreground_service.assert_awaited_once()
        self.assertIsNone(self.runner.error)

    async def test_failure_cleans_up_and_allows_restart(self):
        failure = ValueError("task failed")
        cleanup = AsyncMock()
        await self.runner.start(AsyncMock(side_effect=failure), on_stop=cleanup)
        await self.runner._task
        self.assertIs(self.runner.error, failure)
        cleanup.assert_awaited_once()
        self.service.stop_foreground_service.assert_awaited_once()
        self.assertTrue(await self.runner.start(asyncio.Event().wait))
        self.assertIsNone(self.runner.error)
        await self.runner.stop()

    async def test_cleanup_failure_still_stops_service(self):
        failure = ValueError("cleanup failed")
        await self.runner.start(asyncio.Event().wait, on_stop=AsyncMock(side_effect=failure))
        await self.runner.stop()
        self.service.stop_foreground_service.assert_awaited_once()
        self.assertIs(self.runner.error, failure)

    async def test_native_start_failure_never_starts_work(self):
        self.service.start_foreground_service.side_effect = RuntimeError("denied")
        work = AsyncMock()
        with self.assertRaisesRegex(RuntimeError, "denied"):
            await self.runner.start(work)
        work.assert_not_awaited()
        self.assertFalse(self.runner.running)

    async def test_native_stop_failure_is_visible(self):
        failure = RuntimeError("disconnected")
        self.service.stop_foreground_service.side_effect = failure
        await self.runner.start(asyncio.Event().wait)
        await self.runner.stop()
        self.assertIs(self.runner.error, failure)

    async def test_native_stop_event_cancels_python_work(self):
        cleanup = AsyncMock()
        await self.runner.start(asyncio.Event().wait, on_stop=cleanup)
        await self.service.on_stopped(SimpleNamespace(data='current'))
        self.assertFalse(self.runner.running)
        cleanup.assert_awaited_once()

    async def test_stale_native_stop_event_preserves_new_task(self):
        await self.runner.start(asyncio.Event().wait)
        await self.service.on_stopped(SimpleNamespace(data='previous'))
        self.assertTrue(self.runner.running)
        await self.runner.stop()

    async def test_cancelled_start_waits_for_native_then_rolls_back(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def native_start(**kwargs):
            entered.set()
            await release.wait()

        self.service.start_foreground_service.side_effect = native_start
        work = AsyncMock()
        start = asyncio.create_task(self.runner.start(work))
        await entered.wait()
        start.cancel()
        await asyncio.sleep(0)
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await start
        work.assert_not_awaited()
        self.service.stop_foreground_service.assert_awaited_once()
        self.assertFalse(self.runner.running)

    async def test_cancelled_rejected_start_does_not_stop_another_owner(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def native_start(**kwargs):
            entered.set()
            await release.wait()
            raise RuntimeError("Already owned")

        self.service.start_foreground_service.side_effect = native_start
        start = asyncio.create_task(self.runner.start(AsyncMock()))
        await entered.wait()
        start.cancel()
        await asyncio.sleep(0)
        release.set()
        with self.assertRaises(asyncio.CancelledError):
            await start
        self.service.stop_foreground_service.assert_not_awaited()
        self.assertEqual(str(self.runner.error), "Already owned")

    async def test_cancelled_stop_does_not_interrupt_cleanup(self):
        cleaning = asyncio.Event()
        release = asyncio.Event()

        async def cleanup():
            cleaning.set()
            await release.wait()

        await self.runner.start(asyncio.Event().wait, on_stop=cleanup)
        stop = asyncio.create_task(self.runner.stop())
        await cleaning.wait()
        stop.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await stop
        self.assertTrue(self.runner.running)
        release.set()
        await self.runner._task
        self.service.stop_foreground_service.assert_awaited_once()

    async def test_stop_during_natural_cleanup_preserves_cleanup(self):
        cleaning = asyncio.Event()
        release = asyncio.Event()
        completed = asyncio.Event()

        async def cleanup():
            cleaning.set()
            await release.wait()
            completed.set()

        await self.runner.start(AsyncMock(), on_stop=cleanup)
        await cleaning.wait()
        stop = asyncio.create_task(self.runner.stop())
        await asyncio.sleep(0)
        release.set()
        await stop
        self.assertTrue(completed.is_set())


if __name__ == "__main__":
    unittest.main()
