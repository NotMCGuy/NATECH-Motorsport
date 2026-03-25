from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
import time


class WarningLevel(StrEnum):
    READY = "READY"
    CAUTION = "CAUTION"
    REDLINE = "REDLINE"
    STALE = "STALE"


@dataclass(slots=True)
class TelemetryFrame:
    ignition_on: bool = False
    speed_kph: float = 0.0
    rpm: float = 900.0
    fuel_pct: float = 100.0
    engine_temp_c: float = 88.0
    battery_v: float = 13.6
    trip_km: float = 0.0
    odometer_km: float = 0.0
    gear: str = "N"
    source: str = "SIM"
    captured_at: float = field(default_factory=time.monotonic)


@dataclass(slots=True)
class RuntimeStatus:
    level: WarningLevel = WarningLevel.READY
    message: str = "Nominal"
    updated_at: float = field(default_factory=time.monotonic)
