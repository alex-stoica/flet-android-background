import flet as ft


@ft.control("flet_android_background")
class ForegroundService(ft.Service):
    on_stopped: ft.ControlEventHandler | None = None
    _owner: str | None = None

    async def _call(self, method, **arguments):
        result = await self._invoke_method(method_name=method, arguments=arguments)
        if isinstance(result, dict) and "error" in result:
            raise RuntimeError(result["error"])
        return result

    async def request_permissions(self) -> bool:
        return await self._call("permission")

    async def start_foreground_service(self, *, notification_id=1,
                                       title="Background task", body="Running",
                                       enable_wifi_lock: bool = False,
                                       enable_cpu_lock: bool = False,
                                       cpu_lock_timeout: int = 3600):
        """CPU lock expires after 1–21600 seconds and stops the service."""
        if notification_id <= 0:
            raise ValueError("notification_id must be positive")
        if not isinstance(enable_wifi_lock, bool):
            raise TypeError("enable_wifi_lock must be a bool")
        if not isinstance(enable_cpu_lock, bool):
            raise TypeError("enable_cpu_lock must be a bool")
        if type(cpu_lock_timeout) is not int or not 1 <= cpu_lock_timeout <= 21600:
            raise ValueError("cpu_lock_timeout must be an integer from 1 to 21600 seconds")
        self._owner = await self._call(
            "start", id=notification_id, title=title, body=body,
            enable_wifi_lock=enable_wifi_lock,
            enable_cpu_lock=enable_cpu_lock, cpu_lock_timeout=cpu_lock_timeout,
        )

    async def stop_foreground_service(self):
        await self._call("stop")
