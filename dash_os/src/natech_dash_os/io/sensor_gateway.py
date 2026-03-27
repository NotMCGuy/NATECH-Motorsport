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
    _filtered_throttle: float = 0.0
    _filtered_brake: float = 0.0
    _filtered_clutch: float = 0.0
    _prev_gear: int = 0
    _shift_cut_timer: float = 0.0
    _last_read_at: float = field(default_factory=time.monotonic)

    # Targets for bike-like simulation behavior.
    _top_speed_mph: float = 258.0
    _zero_to_sixty_seconds: float = 2.0

    def set_sim_inputs(self, throttle: float, gear: int, brake: float = 0.0, clutch: float = 0.0, boost: float = 0.0):
        self._sim_throttle = max(0.0, min(1.0, throttle))
        self._sim_gear = max(0, min(6, gear))
        self._sim_brake = max(0.0, min(1.0, brake))
        self._sim_clutch = max(0.0, min(1.0, clutch))
        self._sim_boost = max(0.0, min(1.0, boost))

    def read(self) -> TelemetryFrame:
        t = time.monotonic()
        ignition_on = (t - self.started_at) >= 0.8
        dt = max(0.01, min(0.08, t - self._last_read_at))
        self._last_read_at = t
        top_speed_kph = self._top_speed_mph * 1.609344
        zero_to_sixty_kph = 60.0 * 1.609344
        # The torque curve peaks above 1.0, so apply a calibration factor
        # to land near the requested 0-60 target in practice.
        launch_accel_kph_per_s = (zero_to_sixty_kph / self._zero_to_sixty_seconds) * 0.97

        # Effective gear model tuned for sport-bike style behavior.
        gear_specs = {
            0: {'min': 0, 'max': 0, 'ratio': 0.0},  # Neutral
            1: {'min': 0, 'max': 102, 'ratio': 4.20},
            2: {'min': 20, 'max': 140, 'ratio': 3.10},
            3: {'min': 35, 'max': 185, 'ratio': 2.35},
            4: {'min': 55, 'max': 235, 'ratio': 1.85},
            5: {'min': 70, 'max': 300, 'ratio': 1.45},
            6: {'min': 85, 'max': top_speed_kph, 'ratio': 1.00},
        }
        gear = self._sim_gear
        throttle = self._sim_throttle
        brake = getattr(self, '_sim_brake', 0.0)
        clutch = getattr(self, '_sim_clutch', 0.0)
        boost_input = getattr(self, '_sim_boost', 0.0)

        # Smooth control inputs to remove arcade-like instant jumps.
        smooth_fast = min(1.0, dt * 10.0)
        smooth_medium = min(1.0, dt * 7.0)
        self._filtered_throttle += (throttle - self._filtered_throttle) * smooth_fast
        self._filtered_brake += (brake - self._filtered_brake) * smooth_medium
        self._filtered_clutch += (clutch - self._filtered_clutch) * smooth_medium
        throttle = self._filtered_throttle
        brake = self._filtered_brake
        clutch = self._filtered_clutch

        # Brief torque cut on up/down shifts for a more realistic shift feel.
        if gear != self._prev_gear:
            if self._prev_gear != 0 and gear != 0:
                self._shift_cut_timer = 0.09
            self._prev_gear = gear
        spec = gear_specs[gear]

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
        # Aggressive bike torque curve with stronger launch support.
        def torque_factor(rpm):
            if rpm < 3000:
                return 0.90
            elif rpm < 7000:
                return 0.90 + 0.25 * (rpm - 3000) / 4000
            elif rpm < 10500:
                return 1.15 + 0.20 * (rpm - 7000) / 3500
            elif rpm < 13000:
                return 1.35 - 0.50 * (rpm - 10500) / 2500
            else:
                return 0.0

        max_accel = launch_accel_kph_per_s * (1.0 + 0.20 * (self._turbo_pressure / 2.0))
        max_brake = 20.0
        max_rpm = 13000.0
        prev_speed_kph = self.speed_kph

        if self._shift_cut_timer > 0.0:
            self._shift_cut_timer = max(0.0, self._shift_cut_timer - dt)
            shift_cut_factor = 0.55
        else:
            shift_cut_factor = 1.0

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
            # Net accel in kph/s: launch + torque, with mild aero drag.
            tf = torque_factor(self.rpm)
            # If at or above redline, no more acceleration
            if self.rpm >= max_rpm:
                tf = 0.0
            launch_bonus = 0.0
            if gear == 1 and throttle > 0.85:
                launch_bonus = 4.0 * (1.0 - min(1.0, self.speed_kph / zero_to_sixty_kph))
            drive_accel = max_accel * throttle * tf * shift_cut_factor
            traction_limit = 50.0 if gear == 1 else 44.0 if gear == 2 else 40.0
            if drive_accel > traction_limit:
                drive_accel = traction_limit + (drive_accel - traction_limit) * 0.25
            engine_brake = 5.5 * (1.0 - throttle) * (self.rpm / max_rpm) ** 1.15
            rolling_drag = 1.2 + 0.010 * self.speed_kph
            aero_drag = 11.0 * (self.speed_kph / top_speed_kph) ** 2
            net_accel = (
                drive_accel
                + launch_bonus
                - max_brake * brake
                - aero_drag
                - rolling_drag
                - (engine_brake if clutch < 0.35 else engine_brake * 0.25)
            )
            # Speed update
            target_speed = self.speed_kph + net_accel * dt
            target_speed = max(min_speed, min(max_speed, target_speed))
            self.speed_kph = target_speed
            # Tuned gear-to-rpm mapping so redline aligns with each gear's top speed.
            base_rpm = 1100 + self.speed_kph * spec['ratio'] * 28.5
            # If clutch is pressed, let engine free-rev
            if clutch >= 0.5:
                self.rpm = max(1100.0, min(max_rpm, self.rpm + random.uniform(-50, 50)))
            else:
                self.rpm = max(1100.0, min(max_rpm, base_rpm + random.uniform(-120, 120)))
            # Redline bounce: if throttle and at redline, oscillate
            if self.rpm >= max_rpm and throttle > 0:
                self.rpm = max_rpm - 200 + random.uniform(-100, 100)
        accel_g = (((self.speed_kph - prev_speed_kph) / 3.6) / dt) / 9.80665
        tick_scale = dt / 0.05
        self.fuel_pct = max(0.0, self.fuel_pct - (0.008 * (1 + throttle)) * tick_scale)
        self.trip_km += self.speed_kph / 3600 * dt
        self.odometer_km += self.speed_kph / 3600 * dt

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
            throttle_pct=throttle * 100.0,
            brake_pct=brake * 100.0,
            clutch_pct=clutch * 100.0,
            boost_bar=self._turbo_pressure,
            accel_g=accel_g,
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
