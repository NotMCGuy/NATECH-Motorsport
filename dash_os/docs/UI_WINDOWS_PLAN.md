# NATECH Dash OS - UI Windows Plan

This file tracks scope, data inputs, interactions, and acceptance criteria for each screen/window.

## 1) Boot Window
- Purpose: Play startup media on ignition ON before cluster is visible.
- Inputs: `ignition_on`, boot video asset path.
- Behavior:
  - Ignition OFF -> standby.
  - OFF -> ON transition -> boot video starts.
  - After full playback end -> show Race screen.
- Acceptance:
  - Audio output is active.
  - Video completes naturally (no hard cut).
  - Fallback timeout only for invalid media/decode hangs.

## 2) Standby Window
- Purpose: Safe idle state when ignition is OFF.
- Inputs: `ignition_on`.
- Behavior:
  - Display minimal state and service hint.
  - No telemetry animations.
- Acceptance:
  - Immediate transition from any active screen to standby on ignition OFF.

## 3) Race Window (Primary Drive Screen)
- Purpose: At-a-glance operational cluster while riding.
- Inputs:
  - speed, rpm, gear, fuel_pct, engine_temp_c, battery_v, trip_km, odometer_km
  - warning level/state
- Behavior:
  - Refresh at runtime tick.
  - Warning state visible with priority coloring.
- Acceptance:
  - Readable at distance/glance.
  - Deterministic update order.

### Current implementation status (v0.1)
- Implemented in native UI component: `src/natech_dash_os/ui/race_window.py`
- Implemented now:
  - Central gauge with speed, gear, rpm needle/arc.
  - Left status/rpm cards.
  - Right metrics cards (temp, fuel, battery, trip, odometer).
  - Runtime-connected rendering via `RaceWindow.render(...)`.
- Next polish tasks:
  1. Add branded typography and refined spacing scale.
  2. Add shift-light strip and redline animation behavior.
  3. Add nav strip and right telemetry micro-cards.
  4. Add day/night brightness profile support.

## 4) Telemetry Window
- Purpose: Session and diagnostics telemetry view.
- Planned Inputs:
  - lap times, sector deltas, stale counters, signal timestamps
- Planned Behavior:
  - Structured cards/charts with fixed update cadence.

## 5) Systems Window
- Purpose: Vehicle/runtime health and configuration state.
- Planned Inputs:
  - ECU link state, CAN channel state, watchdog state, profile name
- Planned Behavior:
  - Service-safe controls only.

## 6) Service/Diagnostics Overlay (Planned)
- Purpose: Technician mode for controlled debugging.
- Planned Access:
  - Long-press gesture or authenticated trigger.
- Planned Contents:
  - Signal inspector, dropped frame counters, runtime logs.

## Data Contract Notes
- Runtime store model: `TelemetryFrame`, `RuntimeStatus`.
- Ingest path: Sensor Gateway -> Warning Engine -> Signal Store -> UI refresh.
- Ignition-driven startup is mandatory behavior.

## Current priorities
1. Finalize Race window polish and hierarchy.
2. Build Telemetry window structure.
3. Build Systems window structure.
4. Add service overlay and diagnostics counters.
