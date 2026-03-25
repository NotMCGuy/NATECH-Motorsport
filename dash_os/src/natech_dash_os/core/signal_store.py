from __future__ import annotations

from dataclasses import replace
from threading import Lock
from typing import Callable

from .models import RuntimeStatus, TelemetryFrame



class SignalStore:
    def __init__(self, gateway=None) -> None:
        self._lock = Lock()
        self._frame = TelemetryFrame()
        self._status = RuntimeStatus()
        self._subscribers: list[Callable[[TelemetryFrame, RuntimeStatus], None]] = []
        self.gateway = gateway

    def publish(self, frame: TelemetryFrame, status: RuntimeStatus) -> None:
        with self._lock:
            self._frame = replace(frame)
            self._status = replace(status)
            subscribers = list(self._subscribers)
            frame_copy = replace(self._frame)
            status_copy = replace(self._status)

        for callback in subscribers:
            callback(frame_copy, status_copy)

    def subscribe(self, callback: Callable[[TelemetryFrame, RuntimeStatus], None]) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def snapshot(self) -> tuple[TelemetryFrame, RuntimeStatus]:
        with self._lock:
            return replace(self._frame), replace(self._status)
