import asyncio
import importlib.util
import inspect
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import flet as ft
from flet_android_background import BackgroundTask


class Page:
    def __init__(self, name):
        self.session = SimpleNamespace(id=name)
        self.controls = []
        self.tasks = []

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        pass

    def run_task(self, callback):
        task = asyncio.create_task(callback())
        self.tasks.append(task)
        return task

    async def close(self):
        result = self.on_close(None)
        if inspect.isawaitable(result):
            await result
        await asyncio.sleep(0)

    async def click(self, label):
        for row in self.controls:
            for control in getattr(row, "controls", []):
                if isinstance(control, ft.Button) and control.content == label:
                    await control.on_click(None)
                    await asyncio.sleep(0)
                    return
        raise AssertionError(label)


class DemoSessionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        path = Path(os.environ.get("DEMO_TEST_SOURCE", Path(__file__).parents[1] / "demo.py"))
        spec = importlib.util.spec_from_file_location("session_demo", path)
        self.demo = importlib.util.module_from_spec(spec)
        with patch.object(ft, "run"):
            spec.loader.exec_module(self.demo)
        self.demo.INTEGRATED = False
        self.demo.record = Mock()
        self.runners = []
        self.pages = []

        def create():
            task = BackgroundTask(AsyncMock())
            self.runners.append(task)
            return task

        self.demo.BackgroundTask = create

    async def asyncTearDown(self):
        for task in self.runners:
            await task.on_session_close()
        for page in self.pages:
            for task in page.tasks:
                task.cancel()
            await asyncio.gather(*page.tasks, return_exceptions=True)

    async def page(self, name):
        page = Page(name)
        self.pages.append(page)
        await self.demo.main(page)
        return page

    async def test_close_then_reopen_uses_fresh_runner(self):
        first = await self.page("first")
        await first.click("Start")
        old = self.runners[0]
        self.assertTrue(old.running)
        await first.close()
        self.assertFalse(old.running)
        second = await self.page("second")
        self.assertEqual(len(self.runners), 2)
        await second.click("Start")
        self.assertTrue(self.runners[1].running)
        await first.close()
        self.assertTrue(self.runners[1].running)
        await second.click("Stop")
        self.assertFalse(self.runners[1].running)

    async def test_pause_keeps_work_but_detach_stops_it(self):
        page = await self.page("first")
        await page.click("Start")
        await page.on_app_lifecycle_state_change(SimpleNamespace(state=ft.AppLifecycleState.PAUSE))
        self.assertTrue(self.runners[0].running)
        await page.on_app_lifecycle_state_change(SimpleNamespace(state=ft.AppLifecycleState.DETACH))
        self.assertFalse(self.runners[0].running)
        self.runners[0].service.stop_foreground_service.assert_not_awaited()

    async def test_combined_close_does_not_notify_destroyed_session(self):
        self.demo.INTEGRATED = True
        instances = [AsyncMock(), AsyncMock()]
        module = SimpleNamespace(FletAndroidNotifications=Mock(side_effect=instances))
        with patch.dict("sys.modules", {"flet_android_notifications": module}):
            first = await self.page("first")
            await first.click("Start")
            instances[0].show_notification.reset_mock()
            await first.close()
            instances[0].show_notification.assert_not_awaited()
            second = await self.page("second")
            self.assertEqual(len(self.runners), 2)
            await second.click("Start")
            await first.close()
            self.assertTrue(self.runners[1].running)
            instances[1].show_notification.assert_awaited_once()
