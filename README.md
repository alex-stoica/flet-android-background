# flet-android-background

Experimental foreground tasks for Flet Android. See [Android setup](package/README.md).

```python
import asyncio
import flet as ft
from flet_android_background import BackgroundTask

async def main(page):
    task = BackgroundTask()

    async def start(e):
        # Runs while locked if Android permits. Dismissal or process death stops it. No recovery.
        if await task.service.request_permissions():
            await task.start(lambda: asyncio.sleep(60))

    page.add(
        ft.Button("Start", on_click=start),
        ft.Button("Stop", on_click=lambda e: page.run_task(task.stop)),
    )

ft.run(main)
```

Both demos passed controlled Doze tests on Samsung Galaxy S25.

With uv, Java 17, Android SDK, and Flutter available:

```sh
uv sync
uv run python build.py standalone
uv run python build.py combined
```
