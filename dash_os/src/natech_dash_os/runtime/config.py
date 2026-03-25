from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass(slots=True)
class ThresholdConfig:
    rpm_redline: float
    fuel_low_pct: float
    engine_temp_high_c: float
    battery_low_v: float


@dataclass(slots=True)
class RuntimeConfig:
    stale_timeout_ms: int
    poll_interval_ms: int
    thresholds: ThresholdConfig


def load_runtime_config(path: Path) -> RuntimeConfig:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    thresholds = raw["thresholds"]

    return RuntimeConfig(
        stale_timeout_ms=int(raw["stale_timeout_ms"]),
        poll_interval_ms=int(raw["poll_interval_ms"]),
        thresholds=ThresholdConfig(
            rpm_redline=float(thresholds["rpm_redline"]),
            fuel_low_pct=float(thresholds["fuel_low_pct"]),
            engine_temp_high_c=float(thresholds["engine_temp_high_c"]),
            battery_low_v=float(thresholds["battery_low_v"]),
        ),
    )
