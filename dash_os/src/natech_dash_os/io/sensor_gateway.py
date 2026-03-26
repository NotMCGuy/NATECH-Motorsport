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
    _sim_gear: int = 0  # 0 = Neutral, 1-6 = gears
    _sim_brake: float = 0.0
    _sim_clutch: float = 0.0
    _sim_boost: float = 0.0
    _turbo_pressure: float = 0.0

    def set_sim_inputs(self, throttle: float, gear: int, brake: float = 0.0, clutch: float = 0.0, boost: float = 0.0):
        self._sim_throttle = max(0.0, min(1.0, throttle))
        self._sim_gear = max(0, min(6, gear))
        self._sim_brake = max(0.0, min(1.0, brake))
        self._sim_clutch = max(0.0, min(1.0, clutch))
        self._sim_boost = max(0.0, min(1.0, boost))

    def read(self) -> TelemetryFrame:
        t = time.monotonic()
        ignition_on = (t - self.started_at) >= 0.8
        # Hayabusa 1st-6th gear ratios and specs (approximate)
        gear_specs = {
            0: {'min': 0, 'max': 0, 'ratio': 0.0},  # Neutral
            1: {'min': 0, 'max': 97, 'ratio': 2.615},
            2: {'min': 15, 'max': 137, 'ratio': 1.937},
            3: {'min': 30, 'max': 170, 'ratio': 1.526},
            4: {'min': 45, 'max': 200, 'ratio': 1.285},
            5: {'min': 60, 'max': 230, 'ratio': 1.136},
            6: {'min': 75, 'max': 431, 'ratio': 1.043},  # 431 kph = 268 mph
        }
        gear = self._sim_gear
        throttle = self._sim_throttle
        brake = getattr(self, '_sim_brake', 0.0)
        clutch = getattr(self, '_sim_clutch', 0.0)
        boost_input = getattr(self, '_sim_boost', 0.0)
        spec = gear_specs[gear]
        dt = 0.05  # 50ms tick
        # Turbo boost simulation (0-2.0 bar, laggy, builds with throttle and rpm)
        if not hasattr(self, '_turbo_pressure'):
            self._turbo_pressure = 0.0
        # Turbo boost only applies in top power band (above 9000 RPM)
        if self.rpm > 9000:
            target_boost = min(2.0, (throttle * (self.rpm - 9000) / 4000.0) * (1.0 + 0.7 * boost_input))
        else:
            target_boost = 0.0
        # Turbo lag: pressure builds/decays with time
        lag = 0.18 if target_boost > self._turbo_pressure else 0.08
        self._turbo_pressure += (target_boost - self._turbo_pressure) * lag
        self._turbo_pressure = max(0.0, min(2.0, self._turbo_pressure))
        # Acceleration: 0-60 mph in 1.7s = 15.7 m/s^2, boost adds up to 100%
        # More realistic, aggressive torque curve for Hayabusa
        def torque_factor(rpm):
            # More aggressive launch and realistic top-end drop-off
            if rpm < 3500:
                return 0.45 + 0.22 * (rpm - 1100) / 2400
            elif rpm < 9500:
                return 0.67 + 0.60 * (rpm - 3500) / 6000
            elif rpm < 11000:
                return 1.27 - 0.13 * (rpm - 9500) / 1500
            elif rpm < 13000:
                return 1.08 - 1.08 * (rpm - 11000) / 2000
            else:
                return 0.0

        # Launch: more aggressive for 0-60 mph (1.7s)
        max_accel = 16.5 * (1.0 + 1.2 * (self._turbo_pressure / 2.0))
        max_brake = 16.0  # m/s^2, strong brake
        max_rpm = 13000.0
        if clutch >= 0.5:
            # Free rev, no speed change, no engine braking
            if throttle > 0:
                self.rpm += (max_rpm - self.rpm) * throttle * 0.18
            else:
                self.rpm -= (self.rpm - 1100.0) * 0.12
            self.rpm = max(1100.0, min(max_rpm, self.rpm + random.uniform(-50, 50)))
            # Coast with drag, brake still works
            net_accel = -3.0 - max_brake * brake
            self.speed_kph = max(0.0, self.speed_kph + net_accel * dt)
        elif gear == 0:
            # Neutral: allow revving, no speed increase, coast with drag/brake
            if throttle > 0:
                self.rpm += (max_rpm - self.rpm) * throttle * 0.18
            else:
                self.rpm -= (self.rpm - 1100.0) * 0.12
            self.rpm = max(1100.0, min(max_rpm, self.rpm + random.uniform(-50, 50)))
            net_accel = -3.0 - max_brake * brake
            self.speed_kph = max(0.0, self.speed_kph + net_accel * dt)
        else:
            max_speed = spec['max']
            min_speed = spec['min']
            # Net accel: throttle + turbo - brake, modulated by torque curve
            tf = torque_factor(self.rpm)
            # If at or above redline, no more acceleration
            if self.rpm >= max_rpm:
                tf = 0.0
            net_accel = max_accel * throttle * tf - max_brake * brake
            # Natural drag if no throttle or brake
            if throttle == 0 and brake == 0:
                net_accel = -3.0
            # Speed update
            target_speed = self.speed_kph + net_accel * dt
            target_speed = max(min_speed, min(max_speed, target_speed))
            self.speed_kph = target_speed
            # RPM = idle + speed * gear ratio * factor
            base_rpm = 1100 + self.speed_kph * spec['ratio'] * 60
            # If clutch is pressed, let engine free-rev
            if clutch >= 0.5:
                self.rpm = max(1100.0, min(max_rpm, self.rpm + random.uniform(-50, 50)))
            else:
                self.rpm = max(1100.0, min(max_rpm, base_rpm + random.uniform(-120, 120)))
            # Redline bounce: if throttle and at redline, oscillate
            if self.rpm >= max_rpm and throttle > 0:
                self.rpm = max_rpm - 200 + random.uniform(-100, 100)
        self.fuel_pct = max(0.0, self.fuel_pct - 0.008 * (1 + throttle))
        self.trip_km += self.speed_kph / 3600 / 20
        self.odometer_km += self.speed_kph / 3600 / 20

        return TelemetryFrame(
            ignition_on=ignition_on,
            speed_kph=self.speed_kph,
            rpm=self.rpm,
            fuel_pct=self.fuel_pct,
            engine_temp_c=min(122.0, 82 + self.speed_kph * 0.11),
            battery_v=max(11.7, min(14.5, 13.7 + random.uniform(-0.15, 0.15))),
            trip_km=self.trip_km,
            odometer_km=self.odometer_km,
            gear="N" if gear == 0 else str(gear),
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
