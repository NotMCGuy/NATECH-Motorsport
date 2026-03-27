# NATECH Motorcycle Dash Integration Plan

## 1. Objective
Build a mount-ready motorcycle digital dash system that is:
- Sunlight-readable and vibration-tolerant
- Safe on vehicle power and wiring
- Reliable at boot and runtime
- Correctly bridged to ECU/sensors
- Ready for road/race validation and enclosure mounting

---

## 2. System Architecture (Target)
- Main UI Compute:
  - Raspberry Pi CM4/CM5 class module (Linux + PySide6 UI)
- Real-time I/O + Safety MCU:
  - STM32 with CAN/CAN-FD support, watchdog, and fail-safe outputs
- Data Bridge:
  - STM32 -> CM over UART or SPI (fixed-rate framed telemetry packets)
- Display:
  - 5" to 7" high-brightness panel (>= 1000 nits preferred)
- Inputs:
  - Physical controls (buttons/rotary), optional touch

Rationale:
- UI workload separated from deterministic vehicle I/O
- MCU can continue critical warning handling even if Linux/UI stack stalls

---

## 3. Hardware Needed (v1 to mount on bike)
## Core compute and I/O
- CM4/CM5 carrier board with:
  - reliable storage (industrial microSD or eMMC)
  - GPIO/UART/SPI exposed
- STM32 board (or custom board) with:
  - 2x CAN transceiver paths (or 1x CAN + expansion)
  - UART/SPI link to CM
- CAN transceiver ICs:
  - e.g. MCP2562FD/TJA1051 class

## Power and protection
- 12V bike -> 5V regulated supply:
  - automotive-grade buck converter (wide input, transient resistant)
- Reverse polarity protection stage
- Inline fuse on battery feed
- TVS diode and filtering for load-dump/transients
- Ignition sense line (ACC) for clean boot/shutdown behavior

## Display and enclosure
- Sunlight-readable display (optically bonded if possible)
- Vibration-isolated mounting points
- IP-rated housing target (at least splash resistant)
- Thermal path (passive heatsinking, venting strategy)

## Optional but recommended
- GNSS module for speed/position redundancy
- IMU for lean angle and motion context
- Secondary warning LED/buzzer channel on MCU

---

## 4. ECU Bridging Strategy (critical open area)
This is the highest-risk item and must be solved first.

## Path A: Native CAN bike (preferred)
- Identify bike diagnostic/CAN connector and pinout
- Passive sniff first (no transmit)
- Capture live traffic at idle, rev, movement
- Reverse map frames to signals (RPM, speed, temp, etc.)
- Build DBC (or equivalent mapping table)

## Path B: No accessible CAN or incomplete data
- Read selected signals directly from sensors/lines through MCU:
  - frequency/period inputs (RPM/speed)
  - ADC inputs (temps/pressures via conditioned circuits)
  - digital states (neutral, warnings)
- Requires safe conditioning and filtering circuits

## Path C: Aftermarket ECU integration
- Use ECU output channel/protocol docs
- Prefer documented CAN stream over analog tapping

## Decision gate
Before continuing UI polish, lock one of:
1. CAN frame map ready (best)
2. Sensor tap list + circuit design ready

---

## 5. Dashboard Layout Plan (vehicle-ready)
## Normal mode
- Left dial: speed
- Right dial: RPM (amber/red near redline)
- Center pane: active app/tab content
- Bottom strip: gear + compact speed/RPM + clutch indicator + warning status

## Expanded mode
- Explicit `EXPAND`/`COLLAPSE` button
- Dials animate down/out of view
- Center pane grows for Maps/Media/Diagnostics use
- Keep minimal bottom telemetry visible (speed, RPM, gear, warnings)

## Safety display rule
- Critical warning overlays always take priority over media/maps content

---

## 6. Telemetry Set for Bike Integration
## P0 (must-have for mount test)
- RPM
- Speed
- Gear / neutral
- Coolant temp
- Battery voltage
- Engine warning / MIL state

## P1 (strongly recommended)
- Oil pressure (if available)
- Fuel level/consumption estimate
- Intake temp / manifold pressure
- Throttle position
- Clutch/brake inputs

## P2 (nice-to-have)
- Lean angle (IMU-derived)
- Lap timer and GPS overlays
- Trip analytics and ride logs

---

## 7. Software Work Needed to be mount-ready
## Data pipeline
- Finalize signal schema from ECU/MCU
- Add robust stale-data handling per signal class
- Add telemetry recording/replay format for debugging

## Runtime reliability
- Startup state machine (battery/ignition transitions)
- Graceful shutdown sequence on ignition off
- Watchdog handshake between CM and STM32
- Health monitor and automatic recovery behavior

## UI readiness
- Lock final readability profile (day/night contrast)
- Finalize touch/button interactions with gloves
- Add low-distraction mode for road use

## Media/maps integration hardening
- Spotify OAuth PKCE flow (replace manual token workflow)
- Token refresh and session expiry behavior
- Map provider behavior under low/no connectivity

---

## 8. Electrical + Mechanical Validation Plan
## Bench tests
- Power transients, cold boot, brownout behavior
- End-to-end signal latency and update rates
- Thermal soak test in enclosure

## Bike static tests
- Vibration idle + rev range
- Display visibility in sunlight
- ECU signal correctness at standstill/rev

## Road/track tests
- Signal stability at speed
- Warning correctness under dynamic conditions
- No UI freezes under sustained operation

---

## 9. Immediate next 10 tasks
1. Confirm target motorcycle make/model/year and ECU type.
2. Acquire wiring diagram and connector pinout.
3. Decide ECU bridge path (CAN vs sensor taps).
4. Capture baseline data traces from the bike.
5. Produce first signal mapping table (RPM/speed/temp/gear).
6. Define MCU packet schema to CM.
7. Implement real gateway adapter in `sensor_gateway.py` (non-sim path).
8. Add ignition-safe power state handling and shutdown policy.
9. Build first mount hardware stack (display + power + enclosure mock).
10. Run bench validation checklist and record failures.

---

## 10. Key risks and mitigations
- Unknown ECU access/protocol:
  - Mitigation: prioritize protocol discovery before UI expansion
- Vehicle power noise resets system:
  - Mitigation: automotive power conditioning + brownout strategy
- Overheating in sealed enclosure:
  - Mitigation: thermal budget + heatsink + soak tests
- Rider distraction risk:
  - Mitigation: warning-priority UX and minimal default views

---

## 11. Definition of "Ready to Mount"
System is considered mount-ready when all are true:
- Stable power behavior across start/stop and transients
- Accurate P0 telemetry from real bike sources
- Warnings validated against known fault/threshold scenarios
- Display legible in daylight and vibration tested
- Enclosure/mount passes basic weather and vibration checks
- Recovery behavior defined for sensor loss and UI crash
