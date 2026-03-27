from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QPoint,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QUrl,
    Signal,
)
from PySide6.QtGui import QColor, QConicalGradient, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from natech_dash_os.core.models import RuntimeStatus, TelemetryFrame, WarningLevel
from natech_dash_os.integrations import SpotifyWebApiClient

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:  # pragma: no cover - fallback when WebEngine is unavailable
    QWebEngineView = None


def _asset(relative: str) -> Path:
    return Path(__file__).resolve().parents[3] / "assets" / "qt_reference" / relative


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _warning_color(level: WarningLevel) -> str:
    if level == WarningLevel.REDLINE:
        return "#FF5D5D"
    if level == WarningLevel.CAUTION:
        return "#FFD25A"
    if level == WarningLevel.STALE:
        return "#9AA9BC"
    return "#4AE3A2"


@dataclass(slots=True)
class RaceViewState:
    speed_kph: float
    rpm: float
    gear: str
    fuel_percent: float
    engine_temp_c: float
    boost_bar: float = 0.0
    warning_level: WarningLevel = WarningLevel.READY
    source: str = "SIM"


class SegmentBar(QWidget):
    def __init__(self, segments: int = 7, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.segments = segments
        self.value_ratio = 0.0
        self.color = QColor("#B8FF01")
        self.setMinimumHeight(18)

    def set_value(self, ratio: float) -> None:
        clamped = _clamp(ratio)
        if abs(clamped - self.value_ratio) < 0.01:
            return
        self.value_ratio = clamped
        self.update()

    def set_color(self, color: str) -> None:
        next_color = QColor(color)
        if next_color == self.color:
            return
        self.color = next_color
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        active = int(round(self.value_ratio * self.segments))
        spacing = 3
        available = self.width() - (self.segments - 1) * spacing
        seg_w = max(8, available // self.segments)
        seg_h = max(10, self.height() - 4)

        x = 0
        for idx in range(self.segments):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.color if idx < active else QColor("#01E6DC"))
            painter.drawRect(x, 2, seg_w, seg_h)
            x += seg_w + spacing


class SideGaugeWidget(QWidget):
    def __init__(self, title: str, unit: str, max_value: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.unit = unit
        self.max_value = max_value
        self.value = 0.0
        self.accent = QColor("#B8FF01")
        self.setMinimumSize(280, 280)

    def set_value(self, value: float) -> None:
        next_value = max(0.0, min(self.max_value, value))
        if abs(next_value - self.value) < 0.1:
            return
        self.value = next_value
        self.update()

    def set_accent(self, color: str) -> None:
        next_color = QColor(color)
        if next_color == self.accent:
            return
        self.accent = next_color
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        _ = event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(14, 14, -14, -14)
        center = rect.center()
        radius = min(rect.width(), rect.height()) / 2.0
        ring_radius = radius - 26
        ring_width = max(10.0, radius * 0.14)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(2, 8, 14, 130))
        painter.drawEllipse(center, radius, radius)

        base_pen = QPen(QColor("#163546"), ring_width)
        base_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(base_pen)
        painter.drawArc(
            int(center.x() - ring_radius),
            int(center.y() - ring_radius),
            int(ring_radius * 2),
            int(ring_radius * 2),
            245 * 16,
            -310 * 16,
        )

        ratio = _clamp(self.value / self.max_value)
        if ratio > 0.0:
            grad = QConicalGradient(center, -20)
            grad.setColorAt(0.0, self.accent)
            grad.setColorAt(0.45, self.accent.lighter(120))
            grad.setColorAt(1.0, QColor("#205B79"))
            active_pen = QPen(grad, ring_width)
            active_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(active_pen)
            painter.drawArc(
                int(center.x() - ring_radius),
                int(center.y() - ring_radius),
                int(ring_radius * 2),
                int(ring_radius * 2),
                245 * 16,
                int(-310 * 16 * ratio),
            )

        painter.save()
        painter.translate(center)
        outer = radius - 8
        for i in range(26):
            painter.save()
            angle = -155 + i * (310 / 25)
            painter.rotate(angle)
            is_major = i % 5 == 0
            tick_h = 14 if is_major else 8
            tick_w = 3 if is_major else 2
            mark_ratio = i / 25.0
            on = mark_ratio <= ratio
            painter.setBrush(QColor("#F3F8FF") if on else QColor("#3D4C5F"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(-tick_w // 2, int(-outer), tick_w, tick_h)
            painter.restore()
        painter.restore()

        inner_r = radius * 0.60
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#121B27"))
        painter.drawEllipse(center, inner_r, inner_r)
        painter.setBrush(QColor("#080E15"))
        painter.drawEllipse(center, inner_r * 0.72, inner_r * 0.72)

        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Segoe UI", max(18, int(radius * 0.28)), QFont.Weight.DemiBold))
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), f"{int(self.value):03d}")

        painter.setPen(QColor("#8EA1B8"))
        painter.setFont(QFont("Segoe UI", max(10, int(radius * 0.08)), QFont.Weight.Medium))
        painter.drawText(rect.adjusted(0, int(radius * 0.56), 0, 0), int(Qt.AlignmentFlag.AlignHCenter), self.unit)

        painter.setPen(QColor("#B3C1D3"))
        painter.setFont(QFont("Segoe UI", max(9, int(radius * 0.07)), QFont.Weight.DemiBold))
        painter.drawText(rect.adjusted(0, int(-radius * 0.58), 0, 0), int(Qt.AlignmentFlag.AlignHCenter), self.title)


class TopIconDock(QWidget):
    tab_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._buttons: list[QToolButton] = []

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(10)

        icon_specs = [
            ("icons/bxs_music.svg", "icons/light/bxs_music.svg"),
            ("icons/ep_menu.svg", "icons/light/ep_menu.svg"),
            ("icons/Car_icon.svg", "icons/light/Car_Icon.svg"),
            ("icons/eva_phone-call-fill.svg", "icons/light/eva_phone-call-fill.svg"),
            ("icons/clarity_settings-solid.svg", "icons/light/clarity_settings-solid.svg"),
        ]

        for index, (normal_rel, light_rel) in enumerate(icon_specs):
            button = QToolButton(self)
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(42, 42)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(lambda _checked, idx=index: self.set_active(idx))

            light_icon = _asset(light_rel)
            normal_icon = _asset(normal_rel)
            icon_file = light_icon if (index == 2 and light_icon.exists()) else normal_icon
            if icon_file.exists():
                button.setIcon(QIcon(str(icon_file)))
                button.setIconSize(QSize(24, 24))
            else:
                button.setText("?")

            button.setStyleSheet(
                "QToolButton {background-color: transparent; border: none; border-radius: 21px;}"
                "QToolButton:checked {background-color: rgba(41,190,182,48); border: 1px solid rgba(41,190,182,160);}"
            )
            self._buttons.append(button)
            row.addWidget(button)

        self.set_active(2, emit=False)

    def set_active(self, index: int, emit: bool = True) -> None:
        if index < 0 or index >= len(self._buttons):
            return
        for idx, button in enumerate(self._buttons):
            button.setChecked(idx == index)
        if emit:
            self.tab_changed.emit(index)


class SlidingStackedWidget(QStackedWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_animating = False
        self._anim_group: QParallelAnimationGroup | None = None

    def slide_to(self, index: int) -> None:
        if self._is_animating or index == self.currentIndex() or not (0 <= index < self.count()):
            return

        current_index = self.currentIndex()
        current_widget = self.currentWidget()
        next_widget = self.widget(index)
        if current_widget is None or next_widget is None:
            self.setCurrentIndex(index)
            return

        direction = 1 if index > current_index else -1
        offset = direction * self.width()

        next_widget.setGeometry(self.rect())
        next_widget.move(offset, 0)
        next_widget.show()
        next_widget.raise_()

        current_anim = QPropertyAnimation(current_widget, b"pos", self)
        current_anim.setDuration(240)
        current_anim.setStartValue(current_widget.pos())
        current_anim.setEndValue(QPoint(-offset, 0))
        current_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        next_anim = QPropertyAnimation(next_widget, b"pos", self)
        next_anim.setDuration(240)
        next_anim.setStartValue(next_widget.pos())
        next_anim.setEndValue(QPoint(0, 0))
        next_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        group = QParallelAnimationGroup(self)
        group.addAnimation(current_anim)
        group.addAnimation(next_anim)
        self._anim_group = group
        self._is_animating = True

        def _finish() -> None:
            self.setCurrentIndex(index)
            current_widget.move(0, 0)
            next_widget.move(0, 0)
            self._is_animating = False

        group.finished.connect(_finish)
        group.start()


class WebPane(QWidget):
    def __init__(self, title: str, subtitle: str, url: str, hint: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._url = QUrl(url)
        self._hint_text = hint
        self._loaded = False
        self._web_view = None

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setSpacing(6)

        title_label = QLabel(title, self)
        title_label.setObjectName("pane_title")
        title_label.setStyleSheet("color:#EEF6FF; font-size:24px; font-weight:700;")
        subtitle_label = QLabel(subtitle, self)
        subtitle_label.setObjectName("pane_subtitle")
        subtitle_label.setStyleSheet("color:#7E94B1; font-size:11px; font-weight:600; letter-spacing:1px;")
        self.info_label = QLabel("", self)
        self.info_label.setWordWrap(True)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color:#8EA1B8; font-size:14px; font-weight:600;")
        self.hint_label = QLabel(hint, self)
        self.hint_label.setObjectName("pane_body")
        self.hint_label.setWordWrap(True)
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.content_host = QWidget(self)
        self.content_layout = QVBoxLayout(self.content_host)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        root.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle_label, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.info_label, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self.content_host, 1)
        self.content_layout.addWidget(self.hint_label, alignment=Qt.AlignmentFlag.AlignCenter)

    def ensure_loaded(self) -> None:
        if self._loaded:
            return

        if QWebEngineView is None:
            self.hint_label.setText("Qt WebEngine is not available in this environment.")
            self._loaded = True
            return

        self._web_view = QWebEngineView(self)
        self._web_view.setUrl(self._url)
        self._web_view.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._web_view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self.hint_label.hide()
        self.content_layout.addWidget(self._web_view, 1)
        self._loaded = True

    def set_info(self, text: str, color: str = "#8EA1B8") -> None:
        self.info_label.setText(text)
        self.info_label.setStyleSheet(f"color:{color}; font-size:14px; font-weight:600;")


class SpotifyWidgetPane(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expanded = False
        self._web_loaded = False
        self._web_player: QWebEngineView | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(0)

        self.mode_stack = QStackedWidget(self)
        root.addWidget(self.mode_stack, 1)

        self._compact_page = QWidget(self.mode_stack)
        self._compact_page.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(18,24,20,240), stop:1 rgba(8,12,10,240));"
            "border:1px solid rgba(88,255,172,0.28); border-radius:16px;"
        )
        compact_layout = QVBoxLayout(self._compact_page)
        compact_layout.setContentsMargins(18, 16, 18, 14)
        compact_layout.setSpacing(8)

        compact_title = QLabel("SPOTIFY", self._compact_page)
        compact_title.setStyleSheet("color:#1ED760; font-size:22px; font-weight:800; letter-spacing:1px;")
        compact_subtitle = QLabel("PLAYER", self._compact_page)
        compact_subtitle.setStyleSheet("color:#9BC7AB; font-size:11px; font-weight:700; letter-spacing:1px;")
        self.status = QLabel("Spotify API disconnected", self._compact_page)
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color:#FFD25A; font-size:13px; font-weight:700;")
        self.track = QLabel("--", self._compact_page)
        self.track.setWordWrap(True)
        self.track.setStyleSheet("color:#F5FFF9; font-size:19px; font-weight:800;")
        self.artist = QLabel("--", self._compact_page)
        self.artist.setWordWrap(True)
        self.artist.setStyleSheet("color:#9AB8A2; font-size:13px; font-weight:700;")
        self._compact_progress = QProgressBar(self._compact_page)
        self._compact_progress.setRange(0, 100)
        self._compact_progress.setValue(0)
        self._compact_progress.setTextVisible(False)
        self._compact_progress.setFixedHeight(8)
        self._compact_progress.setStyleSheet(
            "QProgressBar {background-color:rgba(31,40,35,220); border:1px solid #26372F; border-radius:4px;}"
            "QProgressBar::chunk {background-color:#1ED760; border-radius:3px;}"
        )

        compact_controls = QHBoxLayout()
        compact_controls.setSpacing(10)
        self.prev_btn = QPushButton("<<", self._compact_page)
        self.play_btn = QPushButton("Play", self._compact_page)
        self.next_btn = QPushButton(">>", self._compact_page)
        for button in (self.prev_btn, self.play_btn, self.next_btn):
            self._style_transport_button(button)
            compact_controls.addWidget(button)

        compact_layout.addWidget(compact_title)
        compact_layout.addWidget(compact_subtitle)
        compact_layout.addWidget(self.status)
        compact_layout.addWidget(self.track)
        compact_layout.addWidget(self.artist)
        compact_layout.addWidget(self._compact_progress)
        compact_layout.addLayout(compact_controls)
        compact_layout.addStretch(1)

        self._expanded_page = QWidget(self.mode_stack)
        self._expanded_page.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(12,17,15,245), stop:1 rgba(6,10,8,245));"
            "border:1px solid rgba(88,255,172,0.36); border-radius:16px;"
        )
        expanded_layout = QVBoxLayout(self._expanded_page)
        expanded_layout.setContentsMargins(14, 12, 14, 12)
        expanded_layout.setSpacing(10)

        expanded_header = QLabel("SPOTIFY | FULL VIEW", self._expanded_page)
        expanded_header.setStyleSheet("color:#1ED760; font-size:13px; font-weight:800; letter-spacing:1px;")
        self._expanded_status = QLabel("Spotify API disconnected", self._expanded_page)
        self._expanded_status.setStyleSheet("color:#FFD25A; font-size:12px; font-weight:700;")
        self._expanded_status.setWordWrap(True)
        expanded_layout.addWidget(expanded_header)
        expanded_layout.addWidget(self._expanded_status)

        self._web_host = QWidget(self._expanded_page)
        self._web_host_layout = QVBoxLayout(self._web_host)
        self._web_host_layout.setContentsMargins(0, 0, 0, 0)
        self._web_host_layout.setSpacing(0)
        self._web_hint = QLabel(
            "Expanded mode loads Spotify Web Player here.\nInstall PySide6-WebEngine to render the embedded app.",
            self._web_host,
        )
        self._web_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._web_hint.setWordWrap(True)
        self._web_hint.setStyleSheet("color:#8AA196; font-size:13px; font-weight:700;")
        self._web_host_layout.addWidget(self._web_hint, alignment=Qt.AlignmentFlag.AlignCenter)
        expanded_layout.addWidget(self._web_host, 1)

        bottom_player = QWidget(self._expanded_page)
        bottom_player.setStyleSheet(
            "background-color: rgba(13,20,17,220); border:1px solid rgba(76,147,105,0.4); border-radius:12px;"
        )
        bottom_layout = QVBoxLayout(bottom_player)
        bottom_layout.setContentsMargins(12, 10, 12, 10)
        bottom_layout.setSpacing(6)

        self._expanded_track = QLabel("--", bottom_player)
        self._expanded_track.setWordWrap(True)
        self._expanded_track.setStyleSheet("color:#F4FFF9; font-size:17px; font-weight:800;")
        self._expanded_artist = QLabel("--", bottom_player)
        self._expanded_artist.setWordWrap(True)
        self._expanded_artist.setStyleSheet("color:#9AB8A2; font-size:12px; font-weight:700;")
        self._expanded_progress = QProgressBar(bottom_player)
        self._expanded_progress.setRange(0, 100)
        self._expanded_progress.setValue(0)
        self._expanded_progress.setTextVisible(False)
        self._expanded_progress.setFixedHeight(7)
        self._expanded_progress.setStyleSheet(
            "QProgressBar {background-color:rgba(31,40,35,220); border:1px solid #26372F; border-radius:4px;}"
            "QProgressBar::chunk {background-color:#1ED760; border-radius:3px;}"
        )

        expanded_controls = QHBoxLayout()
        expanded_controls.setSpacing(10)
        self._expanded_prev_btn = QPushButton("<<", bottom_player)
        self._expanded_play_btn = QPushButton("Play", bottom_player)
        self._expanded_next_btn = QPushButton(">>", bottom_player)
        for button in (self._expanded_prev_btn, self._expanded_play_btn, self._expanded_next_btn):
            self._style_transport_button(button)
            expanded_controls.addWidget(button)
        self._expanded_prev_btn.clicked.connect(self.prev_btn.click)
        self._expanded_play_btn.clicked.connect(self.play_btn.click)
        self._expanded_next_btn.clicked.connect(self.next_btn.click)

        bottom_layout.addWidget(self._expanded_track)
        bottom_layout.addWidget(self._expanded_artist)
        bottom_layout.addWidget(self._expanded_progress)
        bottom_layout.addLayout(expanded_controls)
        expanded_layout.addWidget(bottom_player)

        self.mode_stack.addWidget(self._compact_page)
        self.mode_stack.addWidget(self._expanded_page)
        self.set_focus_mode(False)

    def _style_transport_button(self, button: QPushButton) -> None:
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(34)
        button.setMinimumWidth(72)
        button.setStyleSheet(
            "QPushButton {background-color: rgba(16,31,24,230); color:#E7FFF0; border:1px solid rgba(60,171,106,0.7);"
            "border-radius:8px; font-size:13px; font-weight:800; padding:4px 10px;}"
            "QPushButton:hover {background-color: rgba(26,49,38,235);}"
            "QPushButton:pressed {background-color: rgba(39,72,56,245);}"
            "QPushButton:disabled {color:#6E8078; border-color:#34463D; background-color:rgba(20,27,24,210);}"
        )

    def _ensure_expanded_web_loaded(self) -> None:
        if self._web_loaded:
            return
        if QWebEngineView is None:
            self._web_hint.setText("Qt WebEngine is not available in this environment.")
            self._web_loaded = True
            return

        self._web_player = QWebEngineView(self._web_host)
        self._web_player.setUrl(QUrl("https://open.spotify.com/"))
        self._web_player.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self._web_player.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self._web_player.setZoomFactor(0.95)
        self._web_hint.hide()
        self._web_host_layout.addWidget(self._web_player, 1)
        self._web_loaded = True

    def set_focus_mode(self, expanded: bool) -> None:
        self._expanded = expanded
        if self._expanded:
            self._ensure_expanded_web_loaded()
            self.mode_stack.setCurrentWidget(self._expanded_page)
        else:
            self.mode_stack.setCurrentWidget(self._compact_page)

    def set_playback_controls_enabled(self, enabled: bool) -> None:
        for button in (
            self.prev_btn,
            self.play_btn,
            self.next_btn,
            self._expanded_prev_btn,
            self._expanded_play_btn,
            self._expanded_next_btn,
        ):
            button.setEnabled(enabled)

    def set_now_playing(self, *, is_playing: bool, track: str, artist: str, progress_pct: int) -> None:
        state = "PLAYING" if is_playing else "PAUSED"
        pct = max(0, min(100, int(progress_pct)))
        status_text = f"{state} ({pct:02d}%)"
        status_color = "#4AE3A2" if is_playing else "#A9B8CA"

        self.status.setText(status_text)
        self.status.setStyleSheet(f"color:{status_color}; font-size:13px; font-weight:700;")
        self._expanded_status.setText(status_text)
        self._expanded_status.setStyleSheet(f"color:{status_color}; font-size:12px; font-weight:700;")

        track_text = track or "--"
        artist_text = artist or "--"
        self.track.setText(track_text)
        self.artist.setText(artist_text)
        self._expanded_track.setText(track_text)
        self._expanded_artist.setText(artist_text)

        self._compact_progress.setValue(pct)
        self._expanded_progress.setValue(pct)

        button_text = "Pause" if is_playing else "Play"
        self.play_btn.setText(button_text)
        self._expanded_play_btn.setText(button_text)

    def set_status(self, text: str, color: str = "#FFD25A") -> None:
        self.status.setText(text)
        self.status.setStyleSheet(f"color:{color}; font-size:13px; font-weight:700;")
        self._expanded_status.setText(text)
        self._expanded_status.setStyleSheet(f"color:{color}; font-size:12px; font-weight:700;")


class RaceWindow(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(1280, 720)
        self.resize(1600, 900)
        self.setStyleSheet("background-color:#000000;")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        self._state = RaceViewState(0.0, 0.0, "N", 100.0, 80.0)
        self._status_message = "Nominal"
        self._active_gear_token = "N"
        self._last_warning_level = WarningLevel.READY
        self._static_scene = QPixmap()
        self._session_top_mph = 0.0
        self._launch_start_ts: float | None = None
        self._zero_to_sixty_s: float | None = None
        self._last_spotify_poll_at = 0.0
        self._spotify_is_playing = False
        self._spotify_device_name = ""
        self._focus_mode = False
        self._layout_anim: QParallelAnimationGroup | None = None

        self._background = QPixmap(str(_asset("icons/Background.png")))
        self._nav_overlay = QPixmap(str(_asset("icons/Top Navigation.svg")))

        self._svg_base = QSvgRenderer(str(_asset("icons/Base.svg")))
        self._svg_left_road = QSvgRenderer(str(_asset("icons/Vector 2.svg")))
        self._svg_right_road = QSvgRenderer(str(_asset("icons/Vector 1.svg")))

        self._base_rect = QRect()
        self._top_nav_rect = QRect()
        self._center_rect = QRect()
        self._speed_strip_rect = QRect()
        self._left_road_rect = QRect()
        self._right_road_rect = QRect()
        self._left_normal_rect = QRect()
        self._left_drop_rect = QRect()
        self._right_normal_rect = QRect()
        self._right_drop_rect = QRect()
        self._segment_normal_rect = QRect()
        self._segment_drop_rect = QRect()
        self._center_normal_rect = QRect()
        self._center_focus_rect = QRect()
        self._expand_normal_rect = QRect()
        self._expand_focus_rect = QRect()

        self.top_dock = TopIconDock(self)
        self.top_dock.tab_changed.connect(self._on_top_tab_changed)

        self.left_gauge = SideGaugeWidget("SPEED", "MPH", 250.0, self)
        self.right_gauge = SideGaugeWidget("RPM", "x100", 130.0, self)
        self.right_gauge.set_accent("#63FFFF")

        self.left_segments = SegmentBar(parent=self)

        self.center_stack = SlidingStackedWidget(self)
        self.center_stack.setStyleSheet(
            "QStackedWidget {background-color: rgba(5, 11, 18, 225); border: 1px solid #1A2C40; border-radius: 18px;}"
            "QLabel#pane_title {color: #EEF6FF; font-size: 34px; font-weight: 700;}"
            "QLabel#pane_subtitle {color: #7E94B1; font-size: 14px; font-weight: 600; letter-spacing: 1px;}"
            "QLabel#pane_body {color: #D8E5F8; font-size: 22px; font-weight: 600;}"
        )
        self.center_stack.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._page_body: dict[str, QLabel] = {}
        self._web_tab_indexes: set[int] = set()
        self._web_panes: dict[str, WebPane] = {}
        self.spotify_widget = SpotifyWidgetPane(self.center_stack)
        self._spotify_tab_index = self.center_stack.addWidget(self.spotify_widget)
        self._create_web_pane(
            "MAPS",
            "GOOGLE MAPS",
            "https://www.google.com/maps",
            "Search route, traffic, and navigation context.",
        )
        self._create_center_pane("RIDE", "PERFORMANCE", "Speed and acceleration")
        self._create_center_pane("PHONE", "SYSTEM", "Warnings and runtime state")
        self._create_center_pane("SETTINGS", "TRIP", "Distance and range")
        self.center_stack.setCurrentIndex(2)

        self._spotify_client = SpotifyWebApiClient.from_environment()
        if self._spotify_client is None:
            self.spotify_widget.set_status(
                "Spotify API disconnected. Set SPOTIFY_ACCESS_TOKEN (PKCE-issued) and optional refresh/client_id vars.",
                "#FFD25A",
            )
            self.spotify_widget.set_playback_controls_enabled(False)
        else:
            self.spotify_widget.set_status("Spotify API connected. Polling playback.", "#4AE3A2")
            self.spotify_widget.set_playback_controls_enabled(True)
        self.spotify_widget.prev_btn.clicked.connect(self._spotify_prev)
        self.spotify_widget.play_btn.clicked.connect(self._spotify_play_pause)
        self.spotify_widget.next_btn.clicked.connect(self._spotify_next)

        self.gear_strip = QWidget(self)
        self.gear_strip.setStyleSheet(
            "background-color: rgba(0,0,0,0);"
            "QLabel {font-size:32px; font-weight:500; color:#6A7687;}"
        )
        gear_layout = QHBoxLayout(self.gear_strip)
        gear_layout.setContentsMargins(0, 0, 0, 0)
        gear_layout.setSpacing(12)
        self.gear_labels: dict[str, QLabel] = {}
        for token in ("1", "N", "2", "3", "4", "5", "6"):
            label = QLabel(token, self.gear_strip)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            gear_layout.addWidget(label)
            self.gear_labels[token] = label

        self.speed_compact = QLabel("SPD ---", self)
        self.speed_compact.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speed_compact.setStyleSheet(
            "color:#EAF4FF; font-size:13px; font-weight:800; background:rgba(10,22,34,0.86); border:1px solid #1D354A; border-radius:10px;"
        )
        self.rpm_compact = QLabel("RPM -----", self)
        self.rpm_compact.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rpm_compact.setStyleSheet(
            "color:#9FD8FF; font-size:13px; font-weight:800; background:rgba(10,22,34,0.86); border:1px solid #1D354A; border-radius:10px;"
        )

        self.status_line = QLabel("READY | NOMINAL | SOURCE SIM", self)
        self.status_line.setStyleSheet("color:#4AE3A2; font-size:15px; font-weight:700;")
        self.status_line.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.metrics_line = QLabel("TEMP 0C    FUEL 0%    BATT 0.0V    BOOST 0.0 bar    ACCEL +0.00g", self)
        self.metrics_line.setStyleSheet("color:#A7B9D0; font-size:14px; font-weight:600;")
        self.metrics_line.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.clutch_indicator = QLabel("CLUTCH OUT", self)
        self.clutch_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clutch_indicator.setStyleSheet(
            "color:#FF5D5D; font-size:13px; font-weight:800; background:rgba(255,93,93,0.16);"
            "border:1px solid rgba(255,93,93,0.55); border-radius:10px; padding:4px 10px;"
        )

        self.expand_button = QPushButton("EXPAND", self)
        self.expand_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.expand_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.expand_button.setStyleSheet(
            "QPushButton {color:#EAF4FF; font-size:13px; font-weight:800; background:rgba(13,33,49,0.9); border:1px solid #2C587A; border-radius:12px; padding:6px 12px;}"
            "QPushButton:hover {background:rgba(22,49,70,0.95);}"
            "QPushButton:pressed {background:rgba(31,67,96,1.0);}"
        )
        self.expand_button.clicked.connect(self.toggle_focus_mode)

        self._set_gear_token("N")

    def _speed_color(self, mph: float) -> str:
        if mph >= 190:
            return "#FF5D5D"
        if mph >= 120:
            return "#FFD25A"
        return "#B8FF01"

    def _rpm_color(self, rpm: float) -> str:
        ratio = _clamp(rpm / 13000.0)
        if ratio >= 0.94:
            return "#FF4040"
        if ratio >= 0.86:
            return "#FFB347"
        return "#63FFFF"

    def toggle_focus_mode(self) -> None:
        self.set_focus_mode(not self._focus_mode)

    def set_focus_mode(self, enabled: bool, *, animated: bool = True) -> None:
        if self._focus_mode == enabled:
            return
        self._focus_mode = enabled
        self.expand_button.setText("COLLAPSE" if self._focus_mode else "EXPAND")
        self.spotify_widget.set_focus_mode(self._focus_mode)
        self._apply_layout_mode(animated=animated)

    def _apply_layout_mode(self, *, animated: bool) -> None:
        left_target = self._left_drop_rect if self._focus_mode else self._left_normal_rect
        right_target = self._right_drop_rect if self._focus_mode else self._right_normal_rect
        segment_target = self._segment_drop_rect if self._focus_mode else self._segment_normal_rect
        center_target = self._center_focus_rect if self._focus_mode else self._center_normal_rect
        expand_target = self._expand_focus_rect if self._focus_mode else self._expand_normal_rect

        if not animated:
            self.left_gauge.setGeometry(left_target)
            self.right_gauge.setGeometry(right_target)
            self.left_segments.setGeometry(segment_target)
            self.center_stack.setGeometry(center_target)
            self.expand_button.setGeometry(expand_target)
            return

        if self._layout_anim is not None:
            self._layout_anim.stop()

        group = QParallelAnimationGroup(self)
        self._layout_anim = group

        for widget, target in (
            (self.left_gauge, left_target),
            (self.right_gauge, right_target),
            (self.left_segments, segment_target),
            (self.center_stack, center_target),
            (self.expand_button, expand_target),
        ):
            anim = QPropertyAnimation(widget, b"geometry", self)
            anim.setDuration(300)
            anim.setStartValue(widget.geometry())
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            group.addAnimation(anim)

        group.start()

    def _create_center_pane(self, title: str, subtitle: str, body: str) -> None:
        page = QWidget(self.center_stack)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        title_label = QLabel(title, page)
        title_label.setObjectName("pane_title")
        subtitle_label = QLabel(subtitle, page)
        subtitle_label.setObjectName("pane_subtitle")
        body_label = QLabel(body, page)
        body_label.setObjectName("pane_body")
        body_label.setWordWrap(True)
        body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(title_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)
        layout.addWidget(body_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)

        self.center_stack.addWidget(page)
        self._page_body[title] = body_label

    def _create_web_pane(self, title: str, subtitle: str, url: str, hint: str) -> None:
        pane = WebPane(title, subtitle, url, hint, self.center_stack)
        index = self.center_stack.addWidget(pane)
        self._web_tab_indexes.add(index)
        self._web_panes[title] = pane

    def _on_top_tab_changed(self, index: int) -> None:
        self.center_stack.slide_to(index)
        widget = self.center_stack.widget(index)
        if hasattr(widget, "ensure_loaded"):
            widget.ensure_loaded()  # type: ignore[union-attr]
        if index == self._spotify_tab_index:
            self.spotify_widget.set_focus_mode(self._focus_mode)
        if index not in self._web_tab_indexes:
            host = self.window()
            if host is not None:
                host.setFocus()

    def _spotify_prev(self) -> None:
        if self._spotify_client is None:
            return
        ok = self._spotify_client.skip_previous()
        if ok:
            self.spotify_widget.set_status("Previous track", "#4AE3A2")
        else:
            err = self._spotify_client.last_error or "Spotify command failed."
            self.spotify_widget.set_status(err, "#FF5D5D")
        self._last_spotify_poll_at = 0.0

    def _spotify_next(self) -> None:
        if self._spotify_client is None:
            return
        ok = self._spotify_client.skip_next()
        if ok:
            self.spotify_widget.set_status("Next track", "#4AE3A2")
        else:
            err = self._spotify_client.last_error or "Spotify command failed."
            self.spotify_widget.set_status(err, "#FF5D5D")
        self._last_spotify_poll_at = 0.0

    def _spotify_play_pause(self) -> None:
        if self._spotify_client is None:
            return
        ok = self._spotify_client.pause_playback() if self._spotify_is_playing else self._spotify_client.start_resume_playback()
        if ok:
            self._spotify_is_playing = not self._spotify_is_playing
            self.spotify_widget.set_status("Playback updated", "#4AE3A2")
        else:
            err = self._spotify_client.last_error or "Spotify command failed."
            self.spotify_widget.set_status(err, "#FF5D5D")
        self._last_spotify_poll_at = 0.0

    def _update_spotify_status(self, captured_at: float) -> None:
        if self._spotify_client is None:
            return
        if (captured_at - self._last_spotify_poll_at) < 2.0:
            return

        self._last_spotify_poll_at = captured_at
        state = self._spotify_client.get_now_playing()
        if state is None:
            err = self._spotify_client.last_error
            if err:
                self.spotify_widget.set_status(err, "#FFD25A")
            else:
                self.spotify_widget.set_status("Spotify: no active playback.", "#FFD25A")
            return

        if state.duration_ms > 0:
            progress_pct = int((state.progress_ms / state.duration_ms) * 100)
        else:
            progress_pct = 0
        self._spotify_is_playing = state.is_playing
        self._spotify_device_name = state.device_name
        self.spotify_widget.set_now_playing(
            is_playing=state.is_playing,
            track=state.track_name,
            artist=state.artists,
            progress_pct=progress_pct,
        )
        device_text = f" on {state.device_name}" if state.device_name else ""
        self.spotify_widget.set_status(f"Spotify connected{device_text}", "#4AE3A2")

    def _set_gear_token(self, gear: str) -> None:
        active = str(gear).upper()
        if active == "0":
            active = "N"
        if active not in self.gear_labels:
            active = "N"
        if active == self._active_gear_token:
            return
        self._active_gear_token = active
        for token, label in self.gear_labels.items():
            if token == active:
                label.setStyleSheet("font-size:32px; font-weight:600; color:#FFFFFF;")
            else:
                label.setStyleSheet("font-size:32px; font-weight:500; color:#6A7687;")

    def _rebuild_static_scene(self) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return

        scene = QPixmap(self.size())
        scene.fill(QColor("#000000"))

        painter = QPainter(scene)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._background.isNull():
            painter.setOpacity(0.92)
            painter.drawPixmap(self.rect(), self._background)
            painter.setOpacity(1.0)

        if self._svg_base.isValid():
            self._svg_base.render(painter, QRectF(self._base_rect))
        else:
            painter.setBrush(QColor(7, 14, 22, 230))
            painter.setPen(QPen(QColor("#1B2736"), 2))
            painter.drawRoundedRect(self._base_rect, 20, 20)

        if not self._nav_overlay.isNull():
            painter.setOpacity(0.95)
            painter.drawPixmap(self._top_nav_rect, self._nav_overlay)
            painter.setOpacity(1.0)

        if self._svg_left_road.isValid():
            self._svg_left_road.render(painter, QRectF(self._left_road_rect))
        if self._svg_right_road.isValid():
            self._svg_right_road.render(painter, QRectF(self._right_road_rect))

        painter.end()
        self._static_scene = scene

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        _ = event
        w, h = self.width(), self.height()

        base_ratio = 1492 / 717
        base_w = int(min(w * 0.92, h * base_ratio * 0.74))
        base_h = int(base_w / base_ratio)
        base_x = (w - base_w) // 2
        base_y = int(h * 0.20)
        self._base_rect = QRect(base_x, base_y, base_w, base_h)

        nav_w = int(base_w * 0.42)
        nav_h = max(58, int(nav_w * 0.16))
        nav_x = base_x + (base_w - nav_w) // 2
        nav_y = base_y - int(nav_h * 1.08)
        self._top_nav_rect = QRect(nav_x, nav_y, nav_w, nav_h)
        self.top_dock.setGeometry(self._top_nav_rect.adjusted(32, 8, -32, -8))

        gauge_size = int(min(base_h * 0.80, w * 0.24))
        gauge_y = base_y + (base_h - gauge_size) // 2 + int(base_h * 0.04)
        left_x = base_x + int(base_w * 0.06)
        right_x = base_x + base_w - int(base_w * 0.06) - gauge_size
        self._left_normal_rect = QRect(left_x, gauge_y, gauge_size, gauge_size)
        self._right_normal_rect = QRect(right_x, gauge_y, gauge_size, gauge_size)
        drop_y = base_y + base_h + int(base_h * 0.10)
        self._left_drop_rect = QRect(left_x, drop_y, gauge_size, gauge_size)
        self._right_drop_rect = QRect(right_x, drop_y, gauge_size, gauge_size)

        center_w = int(base_w * 0.36)
        center_h = int(base_h * 0.56)
        center_x = base_x + (base_w - center_w) // 2
        center_y = base_y + int(base_h * 0.18)
        self._center_normal_rect = QRect(center_x, center_y, center_w, center_h)

        focus_w = int(base_w * 0.66)
        focus_h = int(base_h * 0.72)
        focus_x = base_x + (base_w - focus_w) // 2
        focus_y = base_y + int(base_h * 0.10)
        self._center_focus_rect = QRect(focus_x, focus_y, focus_w, focus_h)
        self._center_rect = self._center_focus_rect if self._focus_mode else self._center_normal_rect

        strip_w = int(base_w * 0.42)
        strip_h = 56
        strip_x = base_x + (base_w - strip_w) // 2
        strip_y = base_y + base_h - strip_h - int(base_h * 0.08)
        self._speed_strip_rect = QRect(strip_x, strip_y, strip_w, strip_h)
        self.gear_strip.setGeometry(self._speed_strip_rect)

        compact_w = int(base_w * 0.11)
        compact_h = 30
        compact_y = strip_y + (strip_h - compact_h) // 2
        self.speed_compact.setGeometry(strip_x - compact_w - 14, compact_y, compact_w, compact_h)
        self.rpm_compact.setGeometry(strip_x + strip_w + 14, compact_y, compact_w, compact_h)

        road_w = int(base_w * 0.085)
        road_h = int(base_h * 0.58)
        road_y = base_y + base_h - road_h - int(base_h * 0.03)
        self._left_road_rect = QRect(strip_x - road_w - int(base_w * 0.08), road_y, road_w, road_h)
        self._right_road_rect = QRect(strip_x + strip_w + int(base_w * 0.08), road_y, road_w, road_h)

        seg_w = int(base_w * 0.15)
        seg_x = base_x + int(base_w * 0.13)
        seg_y = strip_y + int(strip_h * 0.55)
        self._segment_normal_rect = QRect(seg_x, seg_y, seg_w, 14)
        self._segment_drop_rect = QRect(seg_x, drop_y + gauge_size + 12, seg_w, 14)

        clutch_w = int(base_w * 0.16)
        clutch_h = 28
        clutch_x = strip_x - clutch_w - 18
        clutch_y = strip_y + (strip_h - clutch_h) // 2
        self.clutch_indicator.setGeometry(clutch_x, clutch_y, clutch_w, clutch_h)

        expand_w = 118
        expand_h = 34
        self._expand_normal_rect = QRect(
            self._center_normal_rect.right() - expand_w - 8,
            self._center_normal_rect.top() + 8,
            expand_w,
            expand_h,
        )
        self._expand_focus_rect = QRect(
            self._center_focus_rect.right() - expand_w - 8,
            self._center_focus_rect.top() + 8,
            expand_w,
            expand_h,
        )

        status_y = base_y + base_h + 22
        self.status_line.setGeometry(base_x, status_y, base_w, 22)
        self.metrics_line.setGeometry(base_x, status_y + 24, base_w, 20)
        self._apply_layout_mode(animated=False)
        self._rebuild_static_scene()
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        _ = event
        painter = QPainter(self)
        if self._static_scene.isNull():
            self._rebuild_static_scene()
        if not self._static_scene.isNull():
            painter.drawPixmap(0, 0, self._static_scene)
        else:
            painter.fillRect(self.rect(), QColor("#000000"))

    def render(self, frame: TelemetryFrame, status: RuntimeStatus) -> None:
        host = self.window()

        turbo_bar = 0.0
        store = getattr(host, "store", None)
        gateway = getattr(store, "gateway", None)
        if gateway is not None:
            turbo_bar = float(getattr(gateway, "_turbo_pressure", 0.0))

        self._state = RaceViewState(
            speed_kph=frame.speed_kph,
            rpm=frame.rpm,
            gear=str(frame.gear),
            fuel_percent=frame.fuel_pct,
            engine_temp_c=frame.engine_temp_c,
            boost_bar=turbo_bar,
            warning_level=status.level,
            source=frame.source,
        )
        self._status_message = status.message

        mph = frame.speed_kph * 0.621371
        self._session_top_mph = max(self._session_top_mph, mph)
        speed_color = self._speed_color(mph)

        throttle_pct = getattr(frame, "throttle_pct", 0.0)
        brake_pct = getattr(frame, "brake_pct", 0.0)
        clutch_pct = getattr(frame, "clutch_pct", 0.0)
        accel_g = getattr(frame, "accel_g", 0.0)
        self._update_spotify_status(frame.captured_at)

        if throttle_pct > 80.0 and mph < 2.0:
            self._launch_start_ts = frame.captured_at
            self._zero_to_sixty_s = None
        if self._launch_start_ts is not None and self._zero_to_sixty_s is None and mph >= 60.0:
            self._zero_to_sixty_s = max(0.0, frame.captured_at - self._launch_start_ts)
        zero_to_sixty_text = f"{self._zero_to_sixty_s:.2f}s" if self._zero_to_sixty_s is not None else "--"

        self.left_gauge.set_value(mph)
        self.left_gauge.set_accent(speed_color)
        self.speed_compact.setText(f"SPD {int(mph):03d}")

        rpm_scaled = frame.rpm / 100.0
        self.right_gauge.set_value(rpm_scaled)
        rpm_color = self._rpm_color(frame.rpm)
        self.right_gauge.set_accent(rpm_color)
        self.rpm_compact.setText(f"RPM {int(frame.rpm):05d}")
        self.rpm_compact.setStyleSheet(
            f"color:{rpm_color}; font-size:13px; font-weight:800; background:rgba(10,22,34,0.86); border:1px solid #1D354A; border-radius:10px;"
        )

        self.left_segments.set_value(mph / 250.0)
        self.left_segments.set_color(speed_color)

        if clutch_pct >= 70.0:
            self.clutch_indicator.setText("CLUTCH IN  |  SHIFT READY")
            self.clutch_indicator.setStyleSheet(
                "color:#4AE3A2; font-size:13px; font-weight:800; background:rgba(74,227,162,0.16);"
                "border:1px solid rgba(74,227,162,0.55); border-radius:10px; padding:4px 10px;"
            )
        elif clutch_pct >= 25.0:
            self.clutch_indicator.setText("CLUTCH BITING")
            self.clutch_indicator.setStyleSheet(
                "color:#FFD25A; font-size:13px; font-weight:800; background:rgba(255,210,90,0.14);"
                "border:1px solid rgba(255,210,90,0.50); border-radius:10px; padding:4px 10px;"
            )
        else:
            self.clutch_indicator.setText("CLUTCH OUT  |  SHIFT LOCKED")
            self.clutch_indicator.setStyleSheet(
                "color:#FF5D5D; font-size:13px; font-weight:800; background:rgba(255,93,93,0.16);"
                "border:1px solid rgba(255,93,93,0.55); border-radius:10px; padding:4px 10px;"
            )

        self._set_gear_token(str(frame.gear))

        warning = status.level.value
        warning_color = _warning_color(status.level)
        view_mode = "FOCUS" if self._focus_mode else "NORMAL"
        self.status_line.setText(f"{warning} | {status.message.upper()} | SOURCE {frame.source.upper()} | VIEW {view_mode}")
        if status.level != self._last_warning_level:
            self.status_line.setStyleSheet(f"color:{warning_color}; font-size:15px; font-weight:700;")
            self._last_warning_level = status.level

        self.metrics_line.setText(
            f"TEMP {int(frame.engine_temp_c)}C    FUEL {int(frame.fuel_pct)}%    "
            f"BATT {frame.battery_v:.1f}V    BOOST {turbo_bar:.1f} bar    ACCEL {accel_g:+.2f}g"
        )

        self._page_body["RIDE"].setText(
            f"0-60 {zero_to_sixty_text}  |  TOP {self._session_top_mph:06.1f} mph\n"
            f"RPM {int(frame.rpm):05d}  |  ACCEL {accel_g:+.2f}g\n"
            f"THR {throttle_pct:05.1f}%  BRK {brake_pct:05.1f}%  CLT {clutch_pct:05.1f}%"
        )
        self._page_body["PHONE"].setText(
            f"STATUS {status.level.value}  |  SOURCE {frame.source.upper()}\n"
            f"{status.message.upper()}"
        )
        self._page_body["SETTINGS"].setText(
            f"TRIP {frame.trip_km:06.1f} km  |  ODO {frame.odometer_km:07.0f} km\n"
            f"FUEL {int(frame.fuel_pct)}%  |  RANGE {int(frame.fuel_pct * 3.2):03d} km"
        )
