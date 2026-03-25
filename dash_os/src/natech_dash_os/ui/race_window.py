from __future__ import annotations

	def __init__(self, parent: QWidget | None = None, gateway=None) -> None:
		super().__init__(parent)
		self.gateway = gateway
		self.setStyleSheet("background-color:#070A0E;")

		# Main layout
		root = QHBoxLayout(self)
		root.setContentsMargins(0, 0, 0, 0)
		root.setSpacing(0)

		# Sidebar for window switching
		self.sidebar = QFrame()
		self.sidebar.setFixedWidth(90)
		self.sidebar.setStyleSheet("background:rgba(18,22,28,0.92); border-top-right-radius:24px; border-bottom-right-radius:24px; border:1.5px solid #232A36;")
		sidebar_layout = QVBoxLayout(self.sidebar)
		sidebar_layout.setContentsMargins(0, 40, 0, 40)
		sidebar_layout.setSpacing(24)
		# Placeholder buttons for screens
		for label in ["RACE", "TELE", "SYS"]:
			btn = QLabel(label)
			btn.setFixedSize(68, 68)
			btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
			btn.setStyleSheet("background:#181C22; color:#AEE6FF; font-size:22px; font-weight:800; border-radius:18px; border:2px solid #232A36;")
			sidebar_layout.addWidget(btn)
		sidebar_layout.addStretch(1)

		# Central stack for dial
		self.central = QWidget()
		central_layout = QVBoxLayout(self.central)
		central_layout.setContentsMargins(0, 0, 0, 0)
		central_layout.setSpacing(0)

		# Overlay gauge (absolute center)
		gauge_row = QHBoxLayout()
		gauge_row.setContentsMargins(0, 0, 0, 0)
		gauge_row.addStretch(1)
		self.gauge = GaugeWidget()
		self.gauge.setMinimumSize(700, 520)
		self.gauge.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		gauge_row.addWidget(self.gauge, 10)
		gauge_row.addStretch(1)
		central_layout.addLayout(gauge_row, 0)

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

		# Compose sidebar + central
		root.addWidget(self.sidebar, 0)
		root.addWidget(self.central, 10)

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)
		w, h = self.width(), self.height()
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
		super().paintEvent(event)
			int(arc_radius * 2),
			225 * 16,
			-225 * 16,
		)

		# Blue/white arc
		speed_ratio = max(0.0, min(1.0, self.state.speed_kph / 240.0))
		arc_grad = QConicalGradient(center, 225)
		arc_grad.setColorAt(0.0, QColor("#00CFFF"))
		arc_grad.setColorAt(0.7, QColor("#B8E6FF"))
		arc_grad.setColorAt(1.0, QColor("#FFFFFF"))
		arc_pen = QPen(arc_grad, 22)
		arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
		painter.setPen(arc_pen)
		painter.drawArc(
			int(center.x() - arc_radius),
			int(center.y() - arc_radius),
			int(arc_radius * 2),
			int(arc_radius * 2),
			225 * 16,
			int(-225 * 16 * speed_ratio),
		)

		# Central digital value
		font = QFont("Segoe UI", 92, QFont.Weight.Bold)
		painter.setPen(QColor("#F8FAFF"))
		painter.setFont(font)
		painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{int(self.state.speed_kph):02d}")

		# Subtext (kW or KM/H)
		sub_font = QFont("Segoe UI", 22, QFont.Weight.Medium)
		painter.setFont(sub_font)
		painter.setPen(QColor("#00CFFF"))
		painter.drawText(rect.adjusted(0, 80, 0, 0), Qt.AlignmentFlag.AlignHCenter, "KM/H")

		# Range bar (optional, for visual polish)
		# painter.setPen(QPen(QColor("#1B2330"), 6))
		# painter.drawArc(
		#     int(center.x() - arc_radius + 32),
		#     int(center.y() - arc_radius + 32),
		#     int((arc_radius - 32) * 2),
		#     int((arc_radius - 32) * 2),
		#     225 * 16,
		#     int(-225 * 16 * speed_ratio),
		# )


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
		self.setStyleSheet("background-color:#070A0E;")

		# Main layout
		root = QHBoxLayout(self)
		root.setContentsMargins(0, 0, 0, 0)
		root.setSpacing(0)

		# Sidebar for window switching
		self.sidebar = QFrame()
		self.sidebar.setFixedWidth(90)
		self.sidebar.setStyleSheet("background:rgba(18,22,28,0.92); border-top-right-radius:24px; border-bottom-right-radius:24px; border:1.5px solid #232A36;")
		sidebar_layout = QVBoxLayout(self.sidebar)
		sidebar_layout.setContentsMargins(0, 40, 0, 40)
		sidebar_layout.setSpacing(24)
		# Placeholder buttons for screens
		for label in ["RACE", "TELE", "SYS"]:
			btn = QLabel(label)
			btn.setFixedSize(68, 68)
			btn.setAlignment(Qt.AlignmentFlag.AlignCenter)
			btn.setStyleSheet("background:#181C22; color:#AEE6FF; font-size:22px; font-weight:800; border-radius:18px; border:2px solid #232A36;")
			sidebar_layout.addWidget(btn)
		sidebar_layout.addStretch(1)

		# Central stack for background and dial
		self.central = QWidget()
		central_layout = QVBoxLayout(self.central)
		central_layout.setContentsMargins(0, 0, 0, 0)
		central_layout.setSpacing(0)

		# Perspective grid background (drawn in paintEvent)
		self.grid_bg = QWidget()
		self.grid_bg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
		self.grid_bg.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		self.grid_bg.paintEvent = self._paint_grid_bg
		central_layout.addWidget(self.grid_bg, 10)

		# Overlay gauge (absolute center)
		gauge_row = QHBoxLayout()
		gauge_row.setContentsMargins(0, 0, 0, 0)
		gauge_row.addStretch(1)
		self.gauge = GaugeWidget()
		self.gauge.setMinimumSize(700, 520)
		self.gauge.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
		gauge_row.addWidget(self.gauge, 10)
		gauge_row.addStretch(1)
		central_layout.addLayout(gauge_row, 0)

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

		# Compose sidebar + central
		root.addWidget(self.sidebar, 0)
		root.addWidget(self.central, 10)

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
		view_state = RaceViewState(
			speed_kph=frame.speed_kph,
			rpm=frame.rpm,
			gear=frame.gear,
			fuel_percent=frame.fuel_percent,
			engine_temp_c=frame.engine_temp_c,
			lean_angle_deg=frame.lean_angle_deg,
			warning_level=status.level,
			source=frame.source,
		)
		self.gauge.update_state(view_state)
		self.gear_label.setText(str(frame.gear))
		self.range_label.setText(f"{int(frame.trip_km):d} km")
