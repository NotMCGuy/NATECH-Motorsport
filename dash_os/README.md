# NATECH Dash OS (Embedded Runtime Foundation)

This is the non-web application foundation for a vehicle dashboard runtime.

## Scope in this stage
- Native runtime process (`natech_dash_os.runtime`) for telemetry ingest.
- Sensor gateway abstraction for `SIM` and `CAN` sources.
- Deterministic warning engine for priority statuses.
- Native UI entrypoint (PySide6) for HMI integration.

## Not yet production complete
- No watchdog daemon yet.
- No secure OTA/update pipeline yet.
- No redundant failover channel yet.
- CAN decoding map is scaffolded, not final DBC mapping.

## Run (development)
1. `cd dash_os`
2. `python -m pip install -e .`
3. Sim mode UI: `python -m natech_dash_os.main --simulate`
4. Headless runtime: `python -m natech_dash_os.main --simulate --headless`

## Spotify Web API integration (media pane)
- The `MUSIC` tab now has two Spotify layouts:
  - Normal dashboard view: compact Spotify player widget (track, artist, progress, transport buttons)
  - Expanded (`F`) view: embedded Spotify Web Player panel + transport controls
- API paths are aligned to Spotify OpenAPI:
  - `/me/player/currently-playing`, `/me/player/play`, `/me/player/pause`, `/me/player/next`, `/me/player/previous`
- Auth model:
  - Use Authorization Code with PKCE for user tokens (no Implicit Grant)
  - No client secret is used in client-side code
  - Redirect URI validation enforces HTTPS, except loopback `http://127.0.0.1/...` (or `http://[::1]/...`) for local dev
- Token handling:
  - Env bootstrap: `SPOTIFY_ACCESS_TOKEN` (required), `SPOTIFY_CLIENT_ID` (recommended), `SPOTIFY_REFRESH_TOKEN` (optional but recommended)
  - Optional `SPOTIFY_REDIRECT_URI` (default `http://127.0.0.1:8765/callback`)
  - Optional `SPOTIFY_SCOPES` (space-separated override)
  - Optional `SPOTIFY_TOKEN_STORE` path for persisted token cache
  - Auto refresh is used when 401 is returned and refresh credentials are available
- Required minimum scopes for this widget:
  - `user-read-currently-playing`
  - `user-modify-playback-state`
- Rate-limit handling:
  - 429 responses honor `Retry-After` and use exponential backoff

## Simulation controls
- `Up`: throttle
- `Down`: brake
- `Shift`: clutch
- `A` / `Z`: gear up/down (only while clutch is pulled in)
- `F`: toggle focus mode (dials drop down and center pane expands)

## UI test checklist
1. Start with simulation: `python -m natech_dash_os.main --simulate`
2. App opens in fullscreen standby (`IGNITION OFF`).
3. Ignition ON event (simulated automatically after startup) plays `dash_os/assets/boot.mp4`.
4. Boot video audio is enabled (system output device required).
5. Boot video must complete naturally to end-of-media before cluster appears.
6. After boot video completes, cluster view appears and live values update.
7. Press `I` to manually toggle ignition for repeated testing:
   - OFF -> standby
   - ON -> boot video -> cluster

## Custom boot video
- Default file: `dash_os/assets/boot.mp4`
- Override via CLI:
  - `python -m natech_dash_os.main --simulate --boot-video C:/path/to/boot.mp4`

## Folder structure
- `dash_os/src/natech_dash_os/core` -> signal model, warning logic, shared state store
- `dash_os/src/natech_dash_os/io` -> simulated/CAN sensor gateways
- `dash_os/src/natech_dash_os/runtime` -> runtime loop and config loader
- `dash_os/src/natech_dash_os/ui` -> native PySide6 cluster application
- `dash_os/config/runtime.yaml` -> runtime thresholds and polling settings
- `dash_os/assets/boot.mp4` -> ignition boot video
- `dash_os/docs/UI_WINDOWS_PLAN.md` -> planned scope and acceptance criteria per UI window

## Production direction
This runtime is designed to map directly to the target architecture in `ideas.md`:
- CM4/Linux runs this UI/runtime process.
- STM32 handles safety-critical channel and watchdog.
- CAN gateway adapter forwards validated signals into `SignalStore`.
