# NATECH Dash OS Ideas

## Vision
- Build a futuristic motorsport digital dashboard platform for NATECH Motorsports.
- Prioritize race-critical readability, reliability, and fast boot over non-essential features.
- Design a reusable software platform that can scale across multiple cars and drivers.

## Core Goals
- Boot-to-dashboard in under 2 seconds.
- High-performance graphics with smooth animations and clear warning hierarchy.
- Deterministic data handling for CAN and sensor inputs.
- Easy profile switching for car, track, and driver preferences.

## Hardware Direction (Draft)
- Main UI compute: Raspberry Pi Compute Module 4.
- Real-time controller: STM32 for CAN, watchdog, and fail-safe logic.
- Display options: high-brightness 5 to 7 inch IPS panel, sunlight-readable.
- Input options: rotary encoder, steering-wheel buttons, touch (optional).

## Software Architecture Ideas
- Base system: Buildroot Linux on CM4.
- UI framework: Qt 6 + QML for custom futuristic visuals.
- MCU firmware: STM32 handling CAN/CAN-FD and safety-critical alerts.
- IPC bridge between CM4 and STM32 using UART or SPI.
- Modular services:
  - signal decode and processing
  - warning and alarm engine
  - theme and layout engine
  - data logging and playback
  - update and diagnostics

## UI / UX Concepts
- Layered dashboard pages: race, warmup, pits, diagnostics.
- Center focus on speed, RPM bar, gear, and shift lights.
- Peripheral widgets for temps, pressures, fuel, lap delta, and timers.
- Critical warnings always override visual effects.
- Day/night and weather-aware color modes.

## Safety and Reliability
- Hardware watchdog and software health monitor.
- CAN timeout detection with stale-data indicators.
- Safe fallback screen if graphics stack fails.
- Redundant warning channel controlled by STM32.

## Data and Telemetry
- Session logging to SD card.
- Event tagging (overheat, low oil pressure, knock alerts).
- Replay mode for post-session analysis.
- Export format ideas: CSV + binary high-rate logs.

## Open Questions
- Exact display size and resolution target?
- Required CAN protocols and ECUs to support first?
- Target update rate for key signals (RPM, speed, oil pressure)?
- Environmental requirements: vibration, heat, water ingress?
- Need GPS integration in v1 or v2?

## v1 Prototype Scope
- Simulated CAN input for RPM, speed, coolant temp, and oil pressure.
- One primary race screen with warning states.
- Config file for thresholds and colors.
- Basic logging and replay.

## Backlog (Prioritized)
1. Define signal list and message mapping.
2. Build STM32 CAN ingest prototype.
3. Build CM4 dashboard renderer prototype.
4. Implement warning priority state machine.
5. Add profile/config manager.
6. Add logger and replay tools.
7. Add update and diagnostics flow.