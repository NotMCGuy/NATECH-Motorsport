from __future__ import annotations

from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QFrame, QLabel, QSizePolicy
from PySide6.QtGui import QPainter, QColor, QPen, QConicalGradient, QFont

from PySide6.QtCore import Qt, QPoint

from dataclasses import dataclass

# Fix missing imports for enums and models
from natech_dash_os.core.models import WarningLevel, TelemetryFrame, RuntimeStatus

# UI state for the race view
@dataclass
class RaceViewState:
	speed_kph: float
	rpm: float
	gear: int
	fuel_percent: float
	engine_temp_c: float
	lean_angle_deg: float = 0.0
	warning_level: str = "OK"
	source: str = "SIM"


# Card style utility for consistent card backgrounds
def _card_style():
    return (
        "background:#181C22; border-radius:14px; border:1.5px solid #232A36;"
    )


# Functional GaugeWidget for speed, rpm, gear
class GaugeWidget(QWidget):
	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)
		rect = self.rect()
		center = rect.center()
		arc_radius = min(rect.width(), rect.height()) // 2 - 40

		# Draw turbo boost dial (larger, top right, 0-2.0 bar)
		boost_bar = getattr(self.state, 'boost_bar', 0.0)
		boost_radius = 120
		boost_center = rect.topRight() - QPoint(180, -180)
		painter.setPen(QPen(QColor("#FFD25A"), 12))
		painter.setBrush(QColor(255, 210, 90, 80))
		painter.drawEllipse(boost_center, boost_radius, boost_radius)
		# Boost arc
		boost_angle = int(360 * (boost_bar / 2.0))
		painter.setPen(QPen(QColor("#FF5D5D"), 24))
		painter.drawArc(
			boost_center.x() - boost_radius,
			boost_center.y() - boost_radius,
			boost_radius * 2,
			boost_radius * 2,
			90 * 16,
			-boost_angle * 16
		)
		painter.setFont(QFont("Segoe UI", 36, QFont.Bold))
		painter.setPen(QColor("#FFD25A"))
		painter.drawText(boost_center.x() - 80, boost_center.y() + 24, f"TURBO {boost_bar:.1f} bar")

		# Draw background
		painter.setBrush(QColor("#000000"))
		painter.setPen(Qt.NoPen)
		painter.drawEllipse(center, arc_radius, arc_radius)

		if not self.state:
			# Draw placeholder if state is missing
			painter.setPen(QColor("#FFD25A"))
			painter.setFont(QFont("Segoe UI", 48, QFont.Bold))
			painter.drawText(rect, Qt.AlignCenter, "NO DATA")
			return

		# Draw RPM arc with color transition (blue to red)
		max_rpm = 13000.0
		rpm_ratio = min(1.0, self.state.rpm / max_rpm)
		# Interpolate color: blue (#00CFFF) to red (#FF5D5D)
		def lerp_color(c1, c2, t):
			return QColor(
				int(c1.red() + (c2.red() - c1.red()) * t),
				int(c1.green() + (c2.green() - c1.green()) * t),
				int(c1.blue() + (c2.blue() - c1.blue()) * t),
			)
		base_color = QColor("#00CFFF")
		redline_color = QColor("#FF5D5D")
		arc_color = lerp_color(base_color, redline_color, rpm_ratio ** 2)
		arc_pen = QPen(arc_color, 22)
		arc_pen.setCapStyle(Qt.RoundCap)
		painter.setPen(arc_pen)
		painter.drawArc(
			center.x() - arc_radius,
			center.y() - arc_radius,
			arc_radius * 2,
			arc_radius * 2,
			225 * 16,
			int(-225 * 16 * rpm_ratio),
		)

		# Draw throttle, clutch, and brake bars (bottom left/center/right) with percent
		bar_w, bar_h = 220, 28
		margin = 60
		spacing = 40
		# Throttle bar (left)
		throttle = getattr(self.state, 'throttle', 0.0)
		painter.setPen(Qt.NoPen)
		painter.setBrush(QColor("#00CFFF"))
		painter.drawRect(rect.left() + margin, rect.bottom() - margin - bar_h, int(bar_w * throttle), bar_h)
		painter.setBrush(QColor(40, 60, 80, 80))
		painter.drawRect(rect.left() + margin + int(bar_w * throttle), rect.bottom() - margin - bar_h, int(bar_w * (1 - throttle)), bar_h)
		painter.setPen(QColor("#AEE6FF"))
		painter.setFont(QFont("Segoe UI", 18, QFont.Bold))
		painter.drawText(rect.left() + margin, rect.bottom() - margin - bar_h - 8, f"THROTTLE {int(throttle*100)}%")
		# Clutch bar (center)
		clutch = getattr(self.state, 'clutch', 0.0)
		clutch_x = rect.center().x() - bar_w // 2
		painter.setPen(Qt.NoPen)
		painter.setBrush(QColor("#FFD25A"))
		painter.drawRect(clutch_x, rect.bottom() - margin - bar_h, int(bar_w * clutch), bar_h)
		painter.setBrush(QColor(80, 80, 40, 80))
		painter.drawRect(clutch_x + int(bar_w * clutch), rect.bottom() - margin - bar_h, int(bar_w * (1 - clutch)), bar_h)
		painter.setPen(QColor("#FFD25A"))
		painter.setFont(QFont("Segoe UI", 18, QFont.Bold))
		painter.drawText(clutch_x, rect.bottom() - margin - bar_h - 8, f"CLUTCH {int(clutch*100)}%")
		# Brake bar (right)
		brake = getattr(self.state, 'brake', 0.0)
		painter.setPen(Qt.NoPen)
		painter.setBrush(QColor("#FF5D5D"))
		painter.drawRect(rect.right() - margin - bar_w, rect.bottom() - margin - bar_h, int(bar_w * brake), bar_h)
		painter.setBrush(QColor(80, 40, 40, 80))
		painter.drawRect(rect.right() - margin - bar_w + int(bar_w * brake), rect.bottom() - margin - bar_h, int(bar_w * (1 - brake)), bar_h)
		painter.setPen(QColor("#FFD25A"))
		painter.setFont(QFont("Segoe UI", 18, QFont.Bold))
		painter.drawText(rect.right() - margin - bar_w, rect.bottom() - margin - bar_h - 8, f"BRAKE {int(brake*100)}%")

	def __init__(self, parent=None):
		super().__init__(parent)
		self.state = None

	def update_state(self, state):
		self.state = state
		self.update()

	def draw_shift_lights(self, painter, rect, rpm, max_rpm=12000):
		n_lights = 10
		margin = 40
		width = rect.width() - 2 * margin
		y = rect.top() + margin
		light_w = width // n_lights - 4
		light_h = 18
		rpm_per_light = max_rpm / n_lights
		for i in range(n_lights):
			x = rect.left() + margin + i * (light_w + 4)
			on = rpm >= (i + 1) * rpm_per_light
			if rpm >= max_rpm * 0.98:
				color = QColor("#FF5D5D")  # Redline flash
			elif on:
				color = QColor("#FFD25A") if i > 6 else QColor("#00CFFF")
			else:
				color = QColor("#232A36")
			painter.setBrush(color)
			painter.setPen(Qt.NoPen)
			painter.drawRoundedRect(x, y, light_w, light_h, 6, 6)




		# Draw speed (MPH and KPH)
		font = QFont("Segoe UI", 92, QFont.Bold)
		painter.setFont(font)
		painter.setPen(QColor("#F8FAFF"))
		mph = self.state.speed_kph * 0.621371
		painter.drawText(rect, Qt.AlignCenter, f"{int(mph):02d} MPH")
		painter.setFont(QFont("Segoe UI", 38, QFont.Bold))
		painter.setPen(QColor("#AEE6FF"))
		painter.drawText(rect.adjusted(0, 120, 0, 0), Qt.AlignHCenter, f"{int(self.state.speed_kph):02d} KPH")

		# Draw gear (large, centered below speed)
		gear_font = QFont("Segoe UI", 120, QFont.Bold)
		painter.setFont(gear_font)
		painter.setPen(QColor("#FFD25A"))
		# Always display gear as string (handles both int and 'N')
		gear_str = str(self.state.gear) if self.state.gear is not None else "N"
		painter.drawText(rect.adjusted(0, 220, 0, 0), Qt.AlignHCenter, gear_str)





class MetricCard(QFrame):
	def __init__(self, title: str, value: str = "--", unit: str = "") -> None:
		super().__init__()
		self.setStyleSheet(_card_style())
		layout = QVBoxLayout(self)
		layout.setContentsMargins(14, 10, 14, 10)
		layout.setSpacing(2)

		self.title_label = QLabel(title)
		self.title_label.setStyleSheet("color:#8EA1B8; font-size:11px; font-weight:600;")
		self.value_label = QLabel(value)
		self.value_label.setStyleSheet("color:#F5F8FC; font-size:24px; font-weight:800;")
		self.unit_label = QLabel(unit)
		self.unit_label.setStyleSheet("color:#6D7F97; font-size:10px; font-weight:600;")

		layout.addWidget(self.title_label)
		layout.addWidget(self.value_label)
		layout.addWidget(self.unit_label)

	def set_value(self, value: str, unit: str | None = None) -> None:
		self.value_label.setText(value)
		if unit is not None:
			self.unit_label.setText(unit)


class NavPane(QFrame):
	def __init__(self) -> None:
		super().__init__()
		self.setStyleSheet(_card_style())
		layout = QVBoxLayout(self)
		layout.setContentsMargins(14, 14, 14, 14)
		layout.setSpacing(8)

		title = QLabel("RACE")
		title.setStyleSheet("color:#EAF1F8; font-size:18px; font-weight:800;")
		sub = QLabel("SESSION NAV")
		sub.setStyleSheet("color:#6D7F97; font-size:10px; letter-spacing:1px;")
		self.next_turn = QLabel("Next: Straight")
		self.next_turn.setStyleSheet("color:#A9B8CA; font-size:13px; font-weight:600;")
		self.distance = QLabel("Distance: -- m")
		self.distance.setStyleSheet("color:#A9B8CA; font-size:13px; font-weight:600;")

		layout.addWidget(title)
		layout.addWidget(sub)
		layout.addStretch(1)
		layout.addWidget(self.next_turn)
		layout.addWidget(self.distance)

	def set_context(self, speed_kph: float) -> None:
		if speed_kph < 60:
			next_label, dist = "Next: Hairpin", 180
		elif speed_kph < 120:
			next_label, dist = "Next: Chicane", 260
		else:
			next_label, dist = "Next: Straight", 420
		self.next_turn.setText(next_label)
		self.distance.setText(f"Distance: {dist} m")


class StatusStrip(QFrame):
	def __init__(self) -> None:
		super().__init__()
		self.setStyleSheet(
			"background-color:#0D131A; border:1px solid #212a35; border-radius:12px;"
		)
		row = QHBoxLayout(self)
		row.setContentsMargins(14, 10, 14, 10)
		row.setSpacing(16)

		self.mode_label = QLabel("MODE: TRACK")
		self.warn_label = QLabel("READY")
		self.source_label = QLabel("SOURCE: SIM")

		self.mode_label.setStyleSheet("color:#8EA1B8; font-size:12px; font-weight:700;")
		self.source_label.setStyleSheet("color:#8EA1B8; font-size:12px; font-weight:700;")
		self.warn_label.setStyleSheet("color:#4AE3A2; font-size:12px; font-weight:800;")

		row.addWidget(self.mode_label)
		row.addStretch(1)
		row.addWidget(self.warn_label)
		row.addStretch(1)
		row.addWidget(self.source_label)

	def set_status(self, level: WarningLevel, source: str) -> None:
		if level == WarningLevel.REDLINE:
			color = "#FF5D5D"
		elif level == WarningLevel.CAUTION:
			color = "#FFD25A"
		else:
			color = "#4AE3A2"
		self.warn_label.setText(level.value.upper())
		self.warn_label.setStyleSheet(f"color:{color}; font-size:12px; font-weight:800;")
		self.source_label.setText(f"SOURCE: {source.upper()}")


class RaceWindow(QWidget):

	def __init__(self, parent: QWidget | None = None) -> None:
		super().__init__(parent)
		self.setStyleSheet("background-color:#000000;")
		self.setMinimumSize(2520, 1080)
		self.resize(2520, 1080)

		# Main layout
		root = QHBoxLayout(self)
		root.setContentsMargins(0, 0, 0, 0)
		root.setSpacing(0)

		# Sidebar for window switching

		# Central layout with grid and center gauge
		self.central = QWidget()
		central_layout = QVBoxLayout(self.central)
		central_layout.setContentsMargins(0, 0, 0, 0)
		central_layout.setSpacing(0)


		# Center the gauge widget absolutely
		gauge_center_row = QHBoxLayout()
		gauge_center_row.setContentsMargins(0, 0, 0, 0)
		gauge_center_row.addStretch(1)
		self.gauge = GaugeWidget()
		self.gauge.setMinimumSize(900, 900)
		self.gauge.setMaximumSize(1200, 1200)
		self.gauge.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		gauge_center_row.addWidget(self.gauge, 10)
		gauge_center_row.addStretch(1)
		central_layout.addLayout(gauge_center_row, 10)

		# Overlay: top row (status/rpm/nav left, metrics/micro-cards right)
		overlay_row = QHBoxLayout()
		overlay_row.setContentsMargins(40, 40, 40, 40)
		overlay_row.setSpacing(32)

		# Left: status/rpm/nav
		left_col = QVBoxLayout()
		left_col.setSpacing(16)
		self.status_card = QLabel("READY")
		self.status_card.setStyleSheet("color:#4AE3A2; font-size:22px; font-family:'Segoe UI Semibold'; font-weight:800; background:#181C22; border-radius:14px; padding:14px 22px;")
		self.rpm_card = QLabel("RPM: 0")
		self.rpm_card.setStyleSheet("color:#AEE6FF; font-size:20px; font-family:'Segoe UI'; font-weight:700; background:#181C22; border-radius:14px; padding:12px 20px;")
		self.nav_pane = NavPane()
		left_col.addWidget(self.status_card)
		left_col.addWidget(self.rpm_card)
		left_col.addWidget(self.nav_pane)
		left_col.addStretch(1)
		overlay_row.addLayout(left_col, 2)

		overlay_row.addStretch(8)

		# Right: metrics/micro-cards
		right_col = QVBoxLayout()
		right_col.setSpacing(16)
		self.temp_card = QLabel("TEMP: 0°C")
		self.temp_card.setStyleSheet("color:#FFD25A; font-size:20px; font-family:'Segoe UI'; font-weight:700; background:#181C22; border-radius:14px; padding:12px 20px;")
		self.fuel_card = QLabel("FUEL: 0%")
		self.fuel_card.setStyleSheet("color:#AEE6FF; font-size:20px; font-family:'Segoe UI'; font-weight:700; background:#181C22; border-radius:14px; padding:12px 20px;")
		self.batt_card = QLabel("BATT: 0V")
		self.batt_card.setStyleSheet("color:#8EA1B8; font-size:20px; font-family:'Segoe UI'; font-weight:700; background:#181C22; border-radius:14px; padding:12px 20px;")
		self.trip_card = QLabel("TRIP: 0 km")
		self.trip_card.setStyleSheet("color:#8EA1B8; font-size:20px; font-family:'Segoe UI'; font-weight:700; background:#181C22; border-radius:14px; padding:12px 20px;")
		self.odo_card = QLabel("ODO: 0 km")
		self.odo_card.setStyleSheet("color:#8EA1B8; font-size:20px; font-family:'Segoe UI'; font-weight:700; background:#181C22; border-radius:14px; padding:12px 20px;")
		self.micro1 = QLabel("ΔLap: --")
		self.micro1.setStyleSheet("color:#AEE6FF; font-size:13px; font-family:'Segoe UI'; font-weight:600; background:#232A36; border-radius:8px; padding:6px 12px;")
		self.micro2 = QLabel("ΔSector: --")
		self.micro2.setStyleSheet("color:#FFD25A; font-size:13px; font-family:'Segoe UI'; font-weight:600; background:#232A36; border-radius:8px; padding:6px 12px;")
		self.micro3 = QLabel("Signal: --")
		self.micro3.setStyleSheet("color:#8EA1B8; font-size:13px; font-family:'Segoe UI'; font-weight:600; background:#232A36; border-radius:8px; padding:6px 12px;")
		right_col.addWidget(self.temp_card)
		right_col.addWidget(self.fuel_card)
		right_col.addWidget(self.batt_card)
		right_col.addWidget(self.trip_card)
		right_col.addWidget(self.odo_card)
		right_col.addWidget(self.micro1)
		right_col.addWidget(self.micro2)
		right_col.addWidget(self.micro3)
		right_col.addStretch(1)
		overlay_row.addLayout(right_col, 2)

		# Add overlay row on top of central layout
		central_layout.addLayout(overlay_row, 0)

		# Bottom info strip
		self.bottom_strip = QFrame()
		self.bottom_strip.setStyleSheet(
			"background:rgba(10,16,24,0.92); border-radius:18px; border:1.5px solid #1B2330;"
		)
		bottom_layout = QHBoxLayout(self.bottom_strip)
		bottom_layout.setContentsMargins(32, 10, 32, 10)
		bottom_layout.setSpacing(32)

		self.gear_label = QLabel("N")
		self.gear_label.setStyleSheet("color:#AEE6FF; font-size:38px; font-weight:800; letter-spacing:2px;")
		self.mode_label = QLabel("POWER")
		self.mode_label.setStyleSheet("color:#6D7F97; font-size:18px; font-weight:700; letter-spacing:2px;")
		self.range_label = QLabel("-- km")
		self.range_label.setStyleSheet("color:#8EA1B8; font-size:18px; font-weight:700; letter-spacing:2px;")

		bottom_layout.addWidget(self.mode_label)
		bottom_layout.addStretch(1)
		bottom_layout.addWidget(self.range_label)
		bottom_layout.addStretch(1)
		bottom_layout.addWidget(self.gear_label)

		central_layout.addWidget(self.bottom_strip, 0, Qt.AlignmentFlag.AlignBottom)

		root.addWidget(self.central, 1)

	def _paint_grid_bg(self, event):
		painter = QPainter(self.grid_bg)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)
		w, h = self.grid_bg.width(), self.grid_bg.height()
		painter.fillRect(0, 0, w, h, QColor("#10141A"))
		# Perspective grid: vanishing point at center bottom
		grid_color = QColor(180, 190, 200, 38)
		spacing = 38
		vanishing_y = h * 0.82
		vanishing_x = w / 2
		# Draw horizontal lines (closer together at bottom)
		for i in range(18):
			y = vanishing_y - (vanishing_y * (i / 18) ** 1.7)
			painter.setPen(QPen(grid_color, 1))
			painter.drawLine(0, int(y), w, int(y))
		# Draw perspective verticals
		for i in range(-8, 9):
			x0 = vanishing_x + i * spacing
			painter.setPen(QPen(grid_color, 1))
			painter.drawLine(int(x0), int(vanishing_y), int(w / 2), 0)

	def render(self, frame: TelemetryFrame, status: RuntimeStatus) -> None:
		# Get throttle and brake from simulation (if available)
		throttle = getattr(getattr(self.parent(), 'parent', lambda: None)(), '_sim_throttle', 0.0)
		brake = getattr(getattr(self.parent(), 'parent', lambda: None)(), '_sim_brake', 0.0)
		view_state = RaceViewState(
			speed_kph=frame.speed_kph,
			rpm=frame.rpm,
			gear=frame.gear,
			fuel_percent=frame.fuel_pct,
			engine_temp_c=frame.engine_temp_c,
			lean_angle_deg=getattr(frame, 'lean_angle_deg', 0.0),
			warning_level=status.level,
			source=frame.source,
		)
		# Attach throttle/brake/clutch/boost for UI bars
		view_state.throttle = throttle
		view_state.brake = brake
		view_state.clutch = getattr(getattr(self.parent(), 'parent', lambda: None)(), '_sim_clutch', 0.0)
		# Attach turbo pressure for UI
		gw = getattr(getattr(self.parent(), 'parent', lambda: None)(), 'store', None)
		turbo_bar = 0.0
		if gw and hasattr(gw, 'gateway') and hasattr(gw.gateway, '_turbo_pressure'):
			turbo_bar = getattr(gw.gateway, '_turbo_pressure', 0.0)
		view_state.boost_bar = turbo_bar
		self.gauge.update_state(view_state)
		self.status_card.setText(status.level.value.upper())
		if status.level == "REDLINE":
			self.status_card.setStyleSheet("color:#FF5D5D; font-size:18px; font-weight:800; background:#181C22; border-radius:12px; padding:12px 18px;")
		elif status.level == "CAUTION":
			self.status_card.setStyleSheet("color:#FFD25A; font-size:18px; font-weight:800; background:#181C22; border-radius:12px; padding:12px 18px;")
		else:
			self.status_card.setStyleSheet("color:#4AE3A2; font-size:18px; font-weight:800; background:#181C22; border-radius:12px; padding:12px 18px;")
		self.rpm_card.setText(f"RPM: {int(frame.rpm)}")
		self.temp_card.setText(f"TEMP: {int(frame.engine_temp_c)}°C")
		self.fuel_card.setText(f"FUEL: {int(frame.fuel_pct)}%")
		self.batt_card.setText(f"BATT: {frame.battery_v:.1f}V")
		self.trip_card.setText(f"TRIP: {int(frame.trip_km)} km")
		self.odo_card.setText(f"ODO: {int(frame.odometer_km)} km")
		self.gear_label.setText(str(frame.gear))
		self.range_label.setText(f"{int(frame.trip_km):d} km")
