# flet-android-background

Experimental foreground tasks for Flet Android. See [Android setup](package/README.md).

```python
import asyncio
import flet as ft
from flet_android_background import BackgroundTask

async def main(page):
    task = BackgroundTask()
    page.on_close = task.on_session_close

    async def start(e):
        if await task.service.request_permissions():
            await task.start(lambda: asyncio.sleep(30), enable_cpu_lock=True, cpu_lock_timeout=60)

    page.add(
        ft.Button("Start", on_click=start),
        ft.Button("Stop", on_click=lambda e: page.run_task(task.stop)),
    )

ft.run(main)
```

With uv, Java 17, Android SDK, and Flutter available:

```sh
uv sync
uv run python build.py standalone
uv run python build.py combined
```
