from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol
import random
import time

from natech_dash_os.core.models import TelemetryFrame


class SensorGateway(Protocol):
    def read(self) -> TelemetryFrame:
        ...


@dataclass(slots=True)
class SimulatedSensorGateway:
    started_at: float = field(default_factory=time.monotonic)
    speed_kph: float = 0.0
    rpm: float = 1000.0
    fuel_pct: float = 100.0
    trip_km: float = 0.0
    odometer_km: float = 12000.0
    _sim_throttle: float = 0.0
    _sim_gear: int = 1

    def set_sim_inputs(self, throttle: float, gear: int):
        self._sim_throttle = max(0.0, min(1.0, throttle))
        self._sim_gear = max(1, min(6, gear))

    def read(self) -> TelemetryFrame:
        t = time.monotonic()
        ignition_on = (t - self.started_at) >= 0.8
        # Simulate speed and rpm based on throttle and gear
        base_speed = 10 + self._sim_gear * 30
        self.speed_kph = max(0.0, base_speed * self._sim_throttle)
        self.rpm = max(900.0, min(14000.0, 1200 + self.speed_kph * 55 + random.uniform(-220, 220)))
        self.fuel_pct = max(0.0, self.fuel_pct - 0.008 * (1 + self._sim_throttle))
        self.trip_km += self.speed_kph / 3600 / 25
        self.odometer_km += self.speed_kph / 3600 / 25

        return TelemetryFrame(
            ignition_on=ignition_on,
            speed_kph=self.speed_kph,
            rpm=self.rpm,
            fuel_pct=self.fuel_pct,
            engine_temp_c=min(122.0, 82 + self.speed_kph * 0.11),
            battery_v=max(11.7, min(14.5, 13.7 + random.uniform(-0.15, 0.15))),
            trip_km=self.trip_km,
            odometer_km=self.odometer_km,
            gear=str(self._sim_gear),
            source="SIM",
            captured_at=t,
        )


@dataclass(slots=True)
class CanSensorGateway:
    channel: str
    bustype: str = "socketcan"

    def read(self) -> TelemetryFrame:
        raise NotImplementedError(
            "CAN gateway mapping is project-specific. Implement DBC parsing + frame decode before production use."
        )
