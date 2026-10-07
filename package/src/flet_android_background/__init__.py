import asyncio
from collections.abc import Awaitable, Callable

from .service import ForegroundService

Callback = Callable[[], Awaitable[None]]


class BackgroundTask:
    """Run one cooperative task. Process death ends execution without restart."""

    def __init__(self, service: ForegroundService | None = None):
        self.service = service or ForegroundService()
        self.service.on_stopped = self._stopped
        self.error: Exception | None = None
        self._task: asyncio.Task[None] | None = None
        self._work: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self, work: Callback, *, on_stop: Callback | None = None,
                    **notification) -> bool:
        """Start once after notification permission; duplicates return False."""
        async with self._lock:
            if self.running:
                return False
            self.error = None
            starting = asyncio.create_task(self._start_native(notification))
            try:
                failure = await asyncio.shield(starting)
            except asyncio.CancelledError:
                self._task = asyncio.create_task(self._rollback(starting))
                await asyncio.shield(self._task)
                raise
            if failure is not None:
                raise failure
            self._work = asyncio.create_task(self._invoke(work))
            self._task = asyncio.create_task(self._run(self._work, on_stop))
            return True

    async def _invoke(self, work: Callback):
        await work()

    async def _start_native(self, notification):
        try:
            await self.service.start_foreground_service(**notification)
        except Exception as exc:
            return exc

    async def _rollback(self, starting):
        try:
            self.error = await starting
            if self.error is None:
                await self.service.stop_foreground_service()
        except Exception as exc:
            self.error = exc

    async def _run(self, work: asyncio.Task[None], on_stop: Callback | None):
        try:
            await work
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self.error = exc
        finally:
            try:
                if on_stop is not None:
                    await on_stop()
            except Exception as exc:
                self.error = self.error or exc
            finally:
                try:
                    await self.service.stop_foreground_service()
                except Exception as exc:
                    self.error = self.error or exc

    async def stop(self) -> None:
        """Cancel work and await cleanup once."""
        async with self._lock:
            if self.running:
                if self._work is not None:
                    self._work.cancel()
                await asyncio.shield(self._task)

    async def _stopped(self, event):
        async with self._lock:
            if event.data == self.service._owner and self.running:
                if self._work is not None:
                    self._work.cancel()
                await asyncio.shield(self._task)
