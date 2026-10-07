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
                                       title="Background task", body="Running"):
        if notification_id <= 0:
            raise ValueError("notification_id must be positive")
        self._owner = await self._call("start", id=notification_id, title=title, body=body)

    async def stop_foreground_service(self):
        await self._call("stop")
