from __future__ import annotations

import argparse
from pathlib import Path
import threading

from natech_dash_os.core.signal_store import SignalStore
from natech_dash_os.core.warning_engine import WarningEngine
from natech_dash_os.io.sensor_gateway import CanSensorGateway, SimulatedSensorGateway
from natech_dash_os.runtime.app_runtime import DashRuntime
from natech_dash_os.runtime.config import load_runtime_config
from natech_dash_os.ui.native_app import run_native_ui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NATECH Dash OS runtime")
    parser.add_argument("--simulate", action="store_true", help="Use simulated sensor gateway")
    parser.add_argument("--can-channel", default="can0", help="CAN channel for hardware mode")
    parser.add_argument("--headless", action="store_true", help="Run runtime without UI")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parents[2] / "config" / "runtime.yaml"),
        help="Runtime config file",
    )
    parser.add_argument(
        "--boot-video",
        default=str(Path(__file__).resolve().parents[2] / "assets" / "boot.mp4"),
        help="Boot video path used when ignition transitions from OFF to ON",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    config = load_runtime_config(Path(args.config))
    gateway = SimulatedSensorGateway() if args.simulate else CanSensorGateway(channel=args.can_channel)
    store = SignalStore()

    warning_engine = WarningEngine(
        stale_timeout_ms=config.stale_timeout_ms,
        rpm_redline=config.thresholds.rpm_redline,
        fuel_low_pct=config.thresholds.fuel_low_pct,
        engine_temp_high_c=config.thresholds.engine_temp_high_c,
        battery_low_v=config.thresholds.battery_low_v,
    )

    runtime = DashRuntime(
        config=config,
        store=store,
        gateway=gateway,
        warning_engine=warning_engine,
    )

    stop_event = threading.Event()
    runtime_thread = threading.Thread(target=runtime.run_forever, args=(stop_event,), daemon=True)
    runtime_thread.start()

    if args.headless:
        try:
            runtime_thread.join()
        except KeyboardInterrupt:
            stop_event.set()
        return

    try:
        run_native_ui(store, stop_event, Path(args.boot_video))
    finally:
        stop_event.set()


if __name__ == "__main__":
    main()
