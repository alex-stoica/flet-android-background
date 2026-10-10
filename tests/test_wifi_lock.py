import unittest
from unittest.mock import AsyncMock

from flet_android_background import BackgroundTask
from flet_android_background.service import ForegroundService


class WifiLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_and_explicit_option_reach_native_start(self):
        for options, expected in [({}, False), ({"enable_wifi_lock": True}, True)]:
            service = ForegroundService()
            service._invoke_method = AsyncMock(return_value="owner")
            await service.start_foreground_service(**options)
            call = service._invoke_method.call_args.kwargs
            self.assertEqual(call["method_name"], "start")
            self.assertIs(call["arguments"]["enable_wifi_lock"], expected)
            self.assertEqual(service._owner, "owner")

    async def test_invalid_option_never_starts_native_service(self):
        service = ForegroundService()
        service._invoke_method = AsyncMock()
        for value in ["false", 1, None]:
            with self.assertRaises(TypeError):
                await service.start_foreground_service(enable_wifi_lock=value)
        service._invoke_method.assert_not_awaited()

    async def test_lock_failure_does_not_run_python_work(self):
        service = ForegroundService()
        service._invoke_method = AsyncMock(return_value={"error": "lock denied"})
        task = BackgroundTask(service)
        work = AsyncMock()
        with self.assertRaisesRegex(RuntimeError, "lock denied"):
            await task.start(work, enable_wifi_lock=True)
        work.assert_not_awaited()
        self.assertFalse(task.running)

    async def test_task_forwards_option_and_releases_on_completion(self):
        service = ForegroundService()
        service._invoke_method = AsyncMock(return_value="owner")
        task = BackgroundTask(service)
        await task.start(AsyncMock(), enable_wifi_lock=True)
        await task._task
        calls = service._invoke_method.call_args_list
        self.assertTrue(calls[0].kwargs["arguments"]["enable_wifi_lock"])
        self.assertEqual(calls[-1].kwargs["method_name"], "stop")
