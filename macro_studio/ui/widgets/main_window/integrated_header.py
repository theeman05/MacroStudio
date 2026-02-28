from typing import TYPE_CHECKING

import qtawesome as qta
from PySide6.QtCore import Qt

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame, QPushButton

from macro_studio.core.types_and_enums import WorkerState
from macro_studio.ui.shared import StatefulHoverButton, HoverButton, setBtnState, IconColor
from macro_studio.ui.widgets.standalone.selector import EditableSelectorDropdown

if TYPE_CHECKING:
    from macro_studio.core.data import Profile
    from macro_studio.ui.widgets.standalone.approval_event import ApprovalEvent


class IntegratedHeader(QWidget):
    def __init__(self, profile: "Profile", parent=None):
        super().__init__(parent=parent)

        self.profile = profile

        # Horizontal Layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)  # Padding: Left, Top, Right, Bottom
        layout.setSpacing(8)  # Space between items

        # --- LEFT SIDE: Title ---
        self.title_label = QLabel("PROFILE // ")
        self.title_label.setObjectName("header_label")
        self.title_label.setStyleSheet("font-size: 15px;")
        layout.addWidget(self.title_label)

        self.profile_selector = EditableSelectorDropdown()
        self.profile_selector.popup.inactive_icon = "ph.folder"
        self.profile_selector.popup.active_icon = "ph.folder-open"
        self.profile_selector.popup.addSortMode("Alphabetical (A to Z)", lambda name: name.lower())
        self.profile_selector.popup.addSortMode("Alphabetical (Z to A)", lambda name: name.lower(), reverse=True)
        layout.addWidget(self.profile_selector)

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

        self._connectSignals()

    def _connectSignals(self):
        self.profile_selector.selectionChanged.connect(self.profile.load)
        self.profile_selector.renameRequested.connect(self._onRenameRequested)
        self.profile_selector.createRequested.connect(self._onCreateRequested)
        self.profile_selector.duplicateRequested.connect(self._onDuplicateRequested)
        self.profile_selector.deleteRequested.connect(self._onDeleteRequested)

    def _onRenameRequested(self, og_name, event: "ApprovalEvent"):
        new_name = event.value
        if new_name in self.profile.profile_names or not self.profile.renameProfile(og_name, new_name):
            event.ignore("Name already exists")
            return

        event.accept(new_name)

    def _onCreateRequested(self, event: "ApprovalEvent"):
        new_name = event.value
        if new_name in self.profile.profile_names or not self.profile.createProfile(new_name):
            event.ignore("Name already exists")
            return

        event.accept(new_name)

    def _onDuplicateRequested(self, profile_name, event: "ApprovalEvent"):
        new_name = self.profile.duplicateProfile(profile_name)
        if not new_name:
            event.ignore("Name already exists")
            return

        event.accept(new_name)

    def _onDeleteRequested(self, profile_name, event: "ApprovalEvent"):
        if len(self.profile.profile_names) == 1 or not self.profile.deleteProfile(profile_name):
            event.ignore("Cannot delete last profile")
            return

        event.accept(profile_name)

    def loadOnce(self):
        self.profile_selector.populate(self.profile.profile_names)
        self.profile_selector.setCurrentItem(self.profile.name)

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