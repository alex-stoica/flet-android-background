# flet-android-background

Experimental; no process-death recovery. Pip install.

Create `BackgroundTask` per page; set `page.on_close = task.on_session_close`.
Use `await task.start(work, enable_wifi_lock=True)` and `await task.stop()`.
WifiLock: default off; released on exit. Android 14+: foreground/screen-on only;
Power policies apply. `WAKE_LOCK` bundled.

Before building:

```python
from flet_android_background.android import configure_android_project

configure_android_project(path, service_type="dataSync")
```

Types: `dataSync`, `shortService`, `specialUse` (requires `subtype`). Time limits apply.
