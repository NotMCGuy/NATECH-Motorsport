from __future__ import annotations

from dataclasses import dataclass
import threading
import time

from natech_dash_os.core.signal_store import SignalStore
from natech_dash_os.core.warning_engine import WarningEngine
from natech_dash_os.io.sensor_gateway import SensorGateway
from natech_dash_os.runtime.config import RuntimeConfig


@dataclass(slots=True)
class DashRuntime:
    config: RuntimeConfig
    store: SignalStore
    gateway: SensorGateway
    warning_engine: WarningEngine

    def run_forever(self, stop_event: threading.Event) -> None:
        sleep_sec = self.config.poll_interval_ms / 1000
        while not stop_event.is_set():
            frame = self.gateway.read()
            status = self.warning_engine.evaluate(frame)
            self.store.publish(frame, status)
            time.sleep(sleep_sec)
