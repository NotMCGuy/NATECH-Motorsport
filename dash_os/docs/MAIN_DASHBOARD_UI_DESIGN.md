# Main Dashboard UI Design (Reference Alignment)

This document describes the two provided reference designs and defines the main dashboard direction for NATECH Dash OS.

## Design A - Wide Instrument Panel + Context Blocks
(Reference with large centered circular gauge, left mini-map, right metric tiles, bottom status row)

### Visual character
- Wide, cinematic horizontal layout.
- High-contrast dark background with cyan/ice-blue luminous accents.
- Minimal color palette with controlled highlight use.
- Strong center focal point (speed and gear), with information distributed peripherally.

### Structural layout
- Left zone: navigation context (map fragment + route arrow + distance cue).
- Center zone: dominant circular speed gauge with layered tick rings.
- Right zone: compact telemetry tiles (trip, efficiency, range, etc.).
- Bottom strip: lightweight system/context indicators.

### UX strengths
- Excellent glance readability from central speed block.
- Clear hierarchy: center -> side context -> bottom micro-status.
- Works well for sustained riding because secondary data is separated, not mixed into the core gauge.

### Risks to avoid
- Tile density can become cluttered if too many metrics are added.
- Bottom strip should remain sparse; avoid turning it into a menu bar.

---

## Design B - Arc-Focused Cluster + Embedded Navigation
(Reference with right/center arc gauge and left integrated route view)

### Visual character
- More aggressive, instrument-cluster feel.
- Semi-circular illuminated arc with progressive ring segments.
- Navigation presented as part of the gauge composition rather than separate page blocks.

### Structural layout
- Left side: low-contrast route map and route line.
- Right-center: speed value inside a partial ring, with active progress arc.
- Auxiliary micro-data around the gauge perimeter.

### UX strengths
- Feels very “vehicle-native” and purpose-built.
- Arc progress gives immediate speed-state perception.
- Integrates navigation without splitting attention too far from central gauge.

### Risks to avoid
- If arc glow is too heavy, readability drops in daylight.
- Peripheral labels can become too small if over-styled.

---

## Final Main Dashboard Direction (for NATECH)

Use a hybrid:
- Base architecture from Design A (wide panel + balanced information regions).
- Gauge language from Design B (clean luminous arc, layered ring ticks, central numeric speed).

### Primary hierarchy
1. Speed (largest element)
2. Gear + RPM state
3. Navigation next action
4. Safety/health warnings
5. Secondary metrics (fuel/temp/battery/trip/odo)

### Composition blueprint
- Left: navigation pane (map abstraction + next maneuver + distance).
- Center: main arc gauge with numeric speed and gear at center.
- Right: compact health cards (fuel, temp, battery, trip, odometer).
- Bottom: restrained status strip (warnings, mode, key runtime states).

### Interaction model
- No consumer-style web navigation.
- Hard state transitions between windows (Race, Telemetry, Systems).
- Warnings override decorative rendering.

### Color and contrast policy
- Base: near-black surfaces.
- Accent: one primary electric-blue family.
- Warning states only: amber and red.
- No rainbow telemetry colors in the main race view.

### Typography policy
- Numeric first: large, stable-width speed figures.
- Labels are short, uppercase, and low-contrast.
- Avoid decorative fonts; use clean technical sans for readability.

---

## Implementation Notes for current Dash OS

Immediate Race-window targets:
1. Add layered arc ring with major/minor tick hierarchy.
2. Keep center speed as the largest stable UI element.
3. Add left nav pane and right health cards permanently in main layout.
4. Keep bottom strip for warning/mode/system state only.
5. Ensure ignition boot video transitions directly into this screen.

---

## Acceptance Criteria for Main Dashboard

- Driver can read speed and warning state in under 300 ms glance time.
- UI remains readable in high-brightness conditions.
- Main screen has clear center focus with no visual clutter.
- Navigation, health, and warnings are visible without competing with speed.
- Screen feels like embedded vehicle HMI, not a webpage.
