from __future__ import annotations

import time

from .models import RuntimeStatus, TelemetryFrame, WarningLevel


class WarningEngine:
    def __init__(
        self,
        stale_timeout_ms: int,
        rpm_redline: float,
        fuel_low_pct: float,
        engine_temp_high_c: float,
        battery_low_v: float,
    ) -> None:
        self.stale_timeout_sec = stale_timeout_ms / 1000
        self.rpm_redline = rpm_redline
        self.fuel_low_pct = fuel_low_pct
        self.engine_temp_high_c = engine_temp_high_c
        self.battery_low_v = battery_low_v

    def evaluate(self, frame: TelemetryFrame) -> RuntimeStatus:
        age = time.monotonic() - frame.captured_at

        if age > self.stale_timeout_sec:
            return RuntimeStatus(level=WarningLevel.STALE, message="Signal timeout")
        if frame.rpm >= self.rpm_redline:
            return RuntimeStatus(level=WarningLevel.REDLINE, message="Shift now")
        if (
            frame.fuel_pct <= self.fuel_low_pct
            or frame.engine_temp_c >= self.engine_temp_high_c
            or frame.battery_v <= self.battery_low_v
        ):
            return RuntimeStatus(level=WarningLevel.CAUTION, message="Check system thresholds")

        return RuntimeStatus(level=WarningLevel.READY, message="Nominal")
