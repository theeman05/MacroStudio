import qtawesome as qta
from PySide6.QtCore import Qt

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame, QPushButton
from macro_studio.ui.shared import StatefulHoverButton, HoverButton, setBtnState, IconColor
from macro_studio.core.types_and_enums import WorkerState


class IntegratedHeader(QWidget):
    def __init__(self, name, parent=None):
        super().__init__(parent=parent)
        # Horizontal Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)  # Padding: Left, Top, Right, Bottom
        layout.setSpacing(8)  # Space between items

        # --- LEFT SIDE: Title ---
        title_label = QLabel(f"MACRO // {name}")
        title_label.setObjectName("header_label")
        title_label.setStyleSheet("font-size: 15px;")
        layout.addWidget(title_label)

        # Vertical Divider Line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #444;")
        line.setFixedHeight(25)
        layout.addWidget(line)

        # --- CENTER LEFT: Main Controls ---

        self.btn_start = StatefulHoverButton(size=36)
        self.btn_start.addState(WorkerState.IDLE,
                                icon=qta.icon("ph.play-circle-bold", color="#2ea043"),
                                hover_icon=qta.icon("ph.play-circle-bold", color="#3fb950"),
                                tooltip="Start [F6]")
        self.btn_start.addState(WorkerState.RUNNING,
                                icon=qta.icon("ph.pause-circle-bold", color="#d29922"),
                                hover_icon=qta.icon("ph.pause-circle-bold", color="#eac54f"),
                                tooltip="Pause [F6]")
        self.btn_start.addState(WorkerState.PAUSED,
                                icon=qta.icon("ph.play-circle-bold", color=IconColor.SELECTED),
                                hover_icon=qta.icon("ph.play-circle-bold", color=IconColor.SELECTED_HOVER),
                                tooltip="Resume [F6]")

        self.btn_interrupt = HoverButton("mdi.alert-octagon-outline", size=36, normal_color="#F46800", hover_color="#F48E40",
                                         tooltip="Interrupt [F8]")

        self.btn_stop = HoverButton("ph.stop-circle-bold", normal_color="#f44336", hover_color="#F46555", tooltip="Stop [F10]", size=36)

        layout.addWidget(self.btn_start)
        layout.addWidget(self.btn_interrupt)
        layout.addWidget(self.btn_stop)

        # --- SPACER (Pushes Overlay to the right) ---
        layout.addStretch()

        # --- RIGHT SIDE: Overlay Toggle ---
        self.btn_overlay = QPushButton()
        self.btn_overlay.setCheckable(True)
        self.btn_overlay.setChecked(True)
        self.btn_overlay.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_overlay.setFixedWidth(110)

        layout.addWidget(self.btn_overlay)

        self.btn_overlay.clicked.connect(self.toggleOverlayVisual)
        self.toggleOverlayVisual(True)

    def updateStateVisual(self, state: WorkerState):
        is_interrupted = state == WorkerState.INTERRUPTED
        if state.name in self.btn_start.states or is_interrupted:
            setBtnState(self.btn_start, state if not is_interrupted else WorkerState.PAUSED)

        if state == WorkerState.IDLE:
            self.btn_stop.setEnabled(False)
            self.btn_interrupt.setEnabled(False)
        else:
            self.btn_stop.setEnabled(True)
            self.btn_interrupt.setEnabled(not is_interrupted)

    def toggleOverlayVisual(self, is_checked):
        btn_overlay = self.btn_overlay

        if is_checked:
            btn_overlay.setText("Overlay: ON")
            btn_overlay.setStyleSheet("background-color: #d29922; color: #fff;")
        else:
            btn_overlay.setText("Overlay: OFF")
            btn_overlay.setStyleSheet("")