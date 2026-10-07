# flet-android-background

Experimental Flet Android tasks; one owns the foreground service.
Locking permits continued execution; Android restrictions still apply.
Dismissal or runtime loss stops the service. Process death has no recovery.

Install the wheel with pip. Add `BackgroundTask` to your Flet app, then
`await task.start(work)` or `await task.stop()`.

Before building the generated Flutter project:

```python
from flet_android_background.android import configure_android_project

configure_android_project(path, service_type="dataSync")
```

Supported types: `dataSync`, `shortService`, `specialUse`. The latter requires
an app-specific `subtype` explanation. Android time limits apply.
