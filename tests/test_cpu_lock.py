import unittest
from unittest.mock import AsyncMock

from flet_android_background import BackgroundTask
from flet_android_background.service import ForegroundService


class CpuLockTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_off_and_bounded_opt_in(self):
        for options, enabled, timeout in [({}, False, 3600),
                ({"enable_cpu_lock": True, "cpu_lock_timeout": 60}, True, 60)]:
            service = ForegroundService()
            service._invoke_method = AsyncMock(return_value="owner")
            await service.start_foreground_service(**options)
            args = service._invoke_method.call_args.kwargs["arguments"]
            self.assertIs(args["enable_cpu_lock"], enabled)
            self.assertEqual(args["cpu_lock_timeout"], timeout)

    async def test_invalid_options_never_start_service(self):
        service = ForegroundService()
        service._invoke_method = AsyncMock()
        for value in [1, "false", None]:
            with self.assertRaises(TypeError):
                await service.start_foreground_service(enable_cpu_lock=value)
        for value in [0, -1, 21601, True, 1.5, None]:
            with self.assertRaises(ValueError):
                await service.start_foreground_service(cpu_lock_timeout=value)
        service._invoke_method.assert_not_awaited()

    async def test_acquisition_failure_does_not_run_work(self):
        service = ForegroundService()
        service._invoke_method = AsyncMock(return_value={"error": "CPU lock denied"})
        task = BackgroundTask(service)
        work = AsyncMock()
        with self.assertRaisesRegex(RuntimeError, "CPU lock denied"):
            await task.start(work, enable_cpu_lock=True, cpu_lock_timeout=30)
        work.assert_not_awaited()
        self.assertFalse(task.running)
