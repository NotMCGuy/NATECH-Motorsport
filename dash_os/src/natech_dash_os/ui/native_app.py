from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QApplication, QGridLayout, QLabel, QStackedLayout, QWidget

from natech_dash_os.core.signal_store import SignalStore
from natech_dash_os.ui.race_window import RaceWindow


class ClusterWindow(QWidget):
    def __init__(self, store: SignalStore, stop_event: threading.Event, boot_video_path: Path) -> None:
        super().__init__()
        self._sim_throttle = 0.0
        self._sim_gear = 1
        self.store = store
        self.stop_event = stop_event
        self.boot_video_path = boot_video_path
        self.last_ignition_on = False
        self.boot_playing = False
        self.manual_ignition_override: bool | None = None

        self.setWindowTitle("NATECH Dash OS")
        self.setMinimumSize(1280, 720)
        self.setStyleSheet(
            "background-color: #000000; color: #dbe9ff; font-family: Segoe UI;"
            "QLabel#speed {font-size: 96px; font-weight: 700;}"
            "QLabel#gear {font-size: 72px; font-weight: 700; color: #64c3ff;}"
            "QLabel#status {font-size: 28px; font-weight: 700;}"
            "QLabel#meta {font-size: 24px; color: #95adce;}"
            "QLabel#standby {font-size: 34px; font-weight: 700; color: #9fbde9;}"
            "QLabel#hint {font-size: 18px; color: #7895be;}"
        )

        self.stack = QStackedLayout(self)

        self.standby_widget = QWidget()
        standby_layout = QGridLayout(self.standby_widget)
        self.standby_label = QLabel("IGNITION OFF")
        self.standby_label.setObjectName("standby")
        self.hint_label = QLabel("Press I to simulate ignition")
        self.hint_label.setObjectName("hint")
        standby_layout.addWidget(self.standby_label, 0, 0, alignment=Qt.AlignmentFlag.AlignCenter)
        standby_layout.addWidget(self.hint_label, 1, 0, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #000000;")

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setMuted(False)
        self.audio_output.setVolume(1.0)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.mediaStatusChanged.connect(self._on_media_status_changed)
        self.player.durationChanged.connect(self._on_duration_changed)

        self.boot_timeout_timer = QTimer(self)
        self.boot_timeout_timer.setSingleShot(True)
        self.boot_timeout_timer.timeout.connect(self._on_boot_timeout)

        self.cluster_widget = RaceWindow()

        self.stack.addWidget(self.standby_widget)
        self.stack.addWidget(self.video_widget)
        self.stack.addWidget(self.cluster_widget)
        self.stack.setCurrentWidget(self.standby_widget)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(50)

    def refresh(self) -> None:
        frame, status = self.store.snapshot()

        ignition_on = self.manual_ignition_override if self.manual_ignition_override is not None else frame.ignition_on

        if ignition_on and not self.last_ignition_on:
            self._on_ignition_on()
        elif (not ignition_on) and self.last_ignition_on:
            self._on_ignition_off()
        self.last_ignition_on = ignition_on

        if not ignition_on:
            return
        self.cluster_widget.render(frame, status)

    def _on_ignition_on(self) -> None:
        if self.boot_playing:
            return

        if self.boot_video_path.exists():
            self.boot_playing = True
            self.stack.setCurrentWidget(self.video_widget)
            self.player.setSource(QUrl.fromLocalFile(str(self.boot_video_path.resolve())))
            self.player.setPosition(0)
            self.player.play()
            self._arm_boot_timeout(120000)
        else:
            self.stack.setCurrentWidget(self.cluster_widget)

    def _on_ignition_off(self) -> None:
        self.boot_playing = False
        self.boot_timeout_timer.stop()
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        self.stack.setCurrentWidget(self.standby_widget)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._finish_boot_video()
        elif status in {QMediaPlayer.MediaStatus.InvalidMedia, QMediaPlayer.MediaStatus.NoMedia}:
            self._finish_boot_video()

    def _on_duration_changed(self, duration_ms: int) -> None:
        if self.boot_playing and duration_ms > 0:
            self._arm_boot_timeout(duration_ms + 1500)

    def _arm_boot_timeout(self, timeout_ms: int) -> None:
        self.boot_timeout_timer.stop()
        self.boot_timeout_timer.start(timeout_ms)

    def _on_boot_timeout(self) -> None:
        self._finish_boot_video()

    def _finish_boot_video(self) -> None:
        if not self.boot_playing:
            return
        self.boot_playing = False
        self.boot_timeout_timer.stop()
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        self.stack.setCurrentWidget(self.cluster_widget)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        key = event.key()
        # Ignition toggle
        if key == Qt.Key.Key_I:
            if self.manual_ignition_override is None:
                self.manual_ignition_override = True
            else:
                self.manual_ignition_override = not self.manual_ignition_override
            event.accept()
            return
        # Throttle up/down (Up/Down)
        if key == Qt.Key.Key_Up:
            self._sim_throttle = min(1.0, self._sim_throttle + 0.05)
            self._update_sim_inputs()
            event.accept()
            return
        if key == Qt.Key.Key_Down:
            self._sim_throttle = max(0.0, self._sim_throttle - 0.05)
            self._update_sim_inputs()
            event.accept()
            return
        # Gear up/down (A/Z)
        if key == Qt.Key.Key_A:
            self._sim_gear = min(6, self._sim_gear + 1)
            self._update_sim_inputs()
            event.accept()
            return
        if key == Qt.Key.Key_Z:
            self._sim_gear = max(1, self._sim_gear - 1)
            self._update_sim_inputs()
            event.accept()
            return
        super().keyPressEvent(event)

    def _update_sim_inputs(self):
        # Only works if using SimulatedSensorGateway
        gw = getattr(self.store, 'gateway', None)
        if gw and hasattr(gw, 'set_sim_inputs'):
            gw.set_sim_inputs(self._sim_throttle, self._sim_gear)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self.stop_event.set()
        super().closeEvent(event)


def run_native_ui(store: SignalStore, stop_event: threading.Event, boot_video_path: Path) -> None:
    app = QApplication([])
    window = ClusterWindow(store, stop_event, boot_video_path)
    window.showFullScreen()
    app.exec()
