import asyncio
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import flet as ft
from flet_android_background import BackgroundTask

LOG = Path(os.environ.get("FLET_APP_STORAGE_DATA", ".")) / "heartbeats.jsonl"
runner = None
count = 0
last_network = "Not checked"
notifications = None


def record(event, **details):
    entry = dict(event=event, utc=datetime.now(timezone.utc).isoformat(),
                 monotonic=round(time.monotonic(), 3), pid=os.getpid(), **details)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry) + "\n")
    print("BACKGROUND_LAB " + json.dumps(entry), flush=True)


def check_network():
    with urlopen("https://www.gstatic.com/generate_204", timeout=5) as response:
        return str(response.status)


async def heartbeat():
    global count, last_network
    record("started")
    while True:
        count += 1
        record("heartbeat", count=count)
        if count % 5 == 0:
            try:
                last_network = await asyncio.to_thread(check_network)
            except Exception as exc:
                last_network = str(exc)
            record("network", result=last_network)
        await asyncio.sleep(2)


async def cleanup():
    record("cleanup", count=count)
    if notifications is not None:
        await notifications.show_notification(
            notification_id=42, title="Task finished",
            body=f"Recorded {count} Python heartbeats", channel_id="results",
            channel_name="Task results",
        )


async def main(page: ft.Page):
    global runner, notifications
    page.title = "Background + Notifications" if INTEGRATED else "Background Only"
    page.padding = 24
    page.theme_mode = ft.ThemeMode.DARK
    if runner is None:
        runner = BackgroundTask()
        record("launch")
    if INTEGRATED and notifications is None:
        from flet_android_notifications import FletAndroidNotifications
        notifications = FletAndroidNotifications()
    status = ft.Text("Ready", size=24)
    details = ft.Text()
    last_status = None
    visible = asyncio.Event()
    visible.set()

    def refresh():
        nonlocal last_status
        current = (runner.running, count, last_network, str(runner.error or "none"))
        if current == last_status:
            return
        status.value = "Running" if current[0] else "Stopped"
        details.value = (f"Heartbeats: {count}\nNetwork: {last_network}\n"
                         f"Error: {current[3]}")
        page.update()
        last_status = current

    async def live_status():
        while True:
            await visible.wait()
            refresh()
            await asyncio.sleep(1)

    async def lifecycle(e):
        if e.state == ft.AppLifecycleState.RESUME:
            visible.set()
        else:
            visible.clear()
        if e.state == ft.AppLifecycleState.DETACH:
            ui_task.cancel()

    wifi_lock = ft.Switch(label="Request WifiLock", value=False)

    async def start(e):
        try:
            if not await runner.service.request_permissions():
                status.value = "Allow notifications to start"
                page.update()
                return
            record("start_requested", enable_wifi_lock=wifi_lock.value)
            await runner.start(
                heartbeat, on_stop=cleanup, notification_id=41,
                title=page.title, body="Python heartbeat is running",
                enable_wifi_lock=wifi_lock.value,
            )
            if notifications is not None:
                await notifications.show_notification(
                    notification_id=42, title="Task started",
                    body="Both packages are working together",
                    channel_id="results", channel_name="Task results",
                )
            refresh()
        except Exception as exc:
            record("start_error", error=str(exc))
            status.value = str(exc)
            page.update()

    async def stop(e=None):
        await runner.stop()
        refresh()

    page.add(
        ft.Text(page.title.upper(), size=14, color=ft.Colors.CYAN_300),
        status, details, wifi_lock,
        ft.Row([ft.Button("Start", on_click=start), ft.Button("Stop", on_click=stop)]),
        ft.Text("Status updates automatically, including after unlocking.\n"
                "A heartbeat is recorded every 2 seconds; internet is checked every 5 beats."),
        ft.Text("Experimental: Android can stop this process. No automatic restart.",
                color=ft.Colors.AMBER_200),
    )
    refresh()
    ui_task = page.run_task(live_status)
    page.on_app_lifecycle_state_change = lifecycle
    page.on_close = lambda e: ui_task.cancel()


ft.run(main)
