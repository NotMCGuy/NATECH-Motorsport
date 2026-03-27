from __future__ import annotations

import threading
import time
import sys
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, QSequentialAnimationGroup, QTimer, Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QApplication, QGraphicsOpacityEffect, QGridLayout, QLabel, QStackedLayout, QWidget

from natech_dash_os.core.signal_store import SignalStore
from natech_dash_os.ui.race_window import RaceWindow


class ClusterWindow(QWidget):
    def __init__(self, store: SignalStore, stop_event: threading.Event, boot_video_path: Path) -> None:
        super().__init__()
        self._sim_throttle = 0.0
        self._sim_brake = 0.0
        self._sim_gear = 0  # Start in neutral
        self._sim_clutch = 0.0  # 0=engaged, 1=disengaged
        self._sim_boost = 0.0  # 0=off, 1=on
        self.store = store
        self.stop_event = stop_event
        self.boot_video_path = boot_video_path
        self.last_ignition_on = False
        self.boot_playing = False
        self.manual_ignition_override: bool | None = None
        self._last_input_tick = time.monotonic()

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
        # Ensure keyboard focus for simulation controls
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

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
        self.transition_overlay = QWidget(self)
        self.transition_overlay.setStyleSheet("background-color:#000000;")
        self.transition_overlay_effect = QGraphicsOpacityEffect(self.transition_overlay)
        self.transition_overlay.setGraphicsEffect(self.transition_overlay_effect)
        self.transition_overlay.hide()
        self._transition_group: QSequentialAnimationGroup | None = None

        self.stack.addWidget(self.standby_widget)
        self.stack.addWidget(self.video_widget)
        self.stack.addWidget(self.cluster_widget)
        self.stack.setCurrentWidget(self.standby_widget)

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(33)

    def eventFilter(self, watched, event):  # type: ignore[override]
        if event.type() in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            if self._handle_sim_key(event, is_press=event.type() == QEvent.Type.KeyPress):
                return True
        return super().eventFilter(watched, event)

    def _handle_sim_key(self, event, is_press: bool) -> bool:
        key = event.key()
        auto_repeat = event.isAutoRepeat()
        changed = False

        if key == Qt.Key.Key_I and is_press and not auto_repeat:
            if self.manual_ignition_override is None:
                self.manual_ignition_override = True
            else:
                self.manual_ignition_override = not self.manual_ignition_override
            return True

        if key == Qt.Key.Key_Up:
            self._sim_throttle = 1.0 if is_press else 0.0
            changed = True
        elif key == Qt.Key.Key_Space:
            self._sim_boost = 1.0 if is_press else 0.0
            changed = True
        elif key == Qt.Key.Key_Down:
            self._sim_brake = 1.0 if is_press else 0.0
            changed = True
        elif key == Qt.Key.Key_Shift:
            self._sim_clutch = 1.0 if is_press else 0.0
            changed = True
        elif key == Qt.Key.Key_A and is_press and not auto_repeat:
            # Gear-up is only allowed while clutch is pulled in.
            if self._sim_clutch >= 0.5:
                self._sim_gear = min(6, self._sim_gear + 1)
                changed = True
            return True
        elif key == Qt.Key.Key_Z and is_press and not auto_repeat:
            # Gear-down is only allowed while clutch is pulled in.
            if self._sim_clutch >= 0.5:
                self._sim_gear = max(0, self._sim_gear - 1)
                changed = True
            return True
        elif key == Qt.Key.Key_F and is_press and not auto_repeat:
            # Toggle expanded-pane mode (drops dials, expands center pane).
            self.cluster_widget.toggle_focus_mode()
            return True
        else:
            return False

        if changed:
            self._update_sim_inputs()
        return True

    def refresh(self) -> None:
        self._sync_controls_from_keyboard_state()
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

    def _sync_controls_from_keyboard_state(self) -> None:
        # Windows fallback: if release events are swallowed by embedded web content,
        # use physical key state to enforce momentary controls.
        if sys.platform != "win32":
            return
        try:
            import ctypes

            user32 = ctypes.windll.user32

            def _is_down(vk: int) -> bool:
                return bool(user32.GetAsyncKeyState(vk) & 0x8000)

            up_down = _is_down(0x26)  # VK_UP
            down_down = _is_down(0x28)  # VK_DOWN
            shift_down = _is_down(0x10)  # VK_SHIFT
            space_down = _is_down(0x20)  # VK_SPACE

            throttle = 1.0 if up_down else 0.0
            brake = 1.0 if down_down else 0.0
            clutch = 1.0 if shift_down else 0.0
            boost = 1.0 if space_down else 0.0

            if (
                throttle != self._sim_throttle
                or brake != self._sim_brake
                or clutch != self._sim_clutch
                or boost != self._sim_boost
            ):
                self._sim_throttle = throttle
                self._sim_brake = brake
                self._sim_clutch = clutch
                self._sim_boost = boost
                self._update_sim_inputs()
        except Exception:
            return

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
        if self._transition_group is not None:
            self._transition_group.stop()
            self._transition_group = None
        self.transition_overlay.hide()
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
        self._smooth_switch_to_cluster()

    def _smooth_switch_to_cluster(self) -> None:
        self.transition_overlay.setGeometry(self.rect())
        self.transition_overlay.raise_()
        self.transition_overlay.show()
        self.transition_overlay_effect.setOpacity(0.0)

        fade_in = QPropertyAnimation(self.transition_overlay_effect, b"opacity", self)
        fade_in.setDuration(150)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.Type.InOutCubic)

        fade_out = QPropertyAnimation(self.transition_overlay_effect, b"opacity", self)
        fade_out.setDuration(260)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InOutCubic)

        group = QSequentialAnimationGroup(self)
        group.addAnimation(fade_in)
        group.addAnimation(fade_out)
        self._transition_group = group

        def _mid_switch() -> None:
            self.stack.setCurrentWidget(self.cluster_widget)
            self.cluster_widget.setFocus()

        def _finish() -> None:
            self.transition_overlay.hide()
            self._transition_group = None

        fade_in.finished.connect(_mid_switch)
        group.finished.connect(_finish)
        group.start()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        self.transition_overlay.setGeometry(self.rect())
        super().resizeEvent(event)

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if self._handle_sim_key(event, is_press=True):
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._handle_sim_key(event, is_press=False):
            event.accept()
            return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        # Safety reset if focus changes while a control key is held.
        self._sim_throttle = 0.0
        self._sim_brake = 0.0
        self._sim_clutch = 0.0
        self._sim_boost = 0.0
        self._update_sim_inputs()
        super().focusOutEvent(event)

    def _update_sim_inputs(self):
        # Only works if using SimulatedSensorGateway
        gw = getattr(self.store, 'gateway', None)
        if gw and hasattr(gw, 'set_sim_inputs'):
            brake = getattr(self, '_sim_brake', 0.0)
            clutch = getattr(self, '_sim_clutch', 0.0)
            boost = getattr(self, '_sim_boost', 0.0)
            gw.set_sim_inputs(self._sim_throttle, self._sim_gear, brake, clutch, boost)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        self.stop_event.set()
        super().closeEvent(event)


def run_native_ui(store: SignalStore, stop_event: threading.Event, boot_video_path: Path) -> None:
    app = QApplication([])
    window = ClusterWindow(store, stop_event, boot_video_path)
    window.showFullScreen()
    app.exec()
