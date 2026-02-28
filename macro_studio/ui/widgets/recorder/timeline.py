import shiboken6

from typing import TYPE_CHECKING, Union
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QListWidget, QAbstractItemView, QCheckBox, QListWidgetItem, QApplication,
)
from PySide6.QtGui import QDrag, QPainter, QColor, QPen, QBrush, QEnterEvent
from PySide6.QtCore import Qt, QItemSelection, QTimer, QPoint, QEvent

from macro_studio.core.recording import ActionType, TimelineStep
from .recorder_main import (createIconLabel, HoverButton, createQtIcon, TRASH_ICON, GRIP_CONFIG, ACTION_TYPES,
                            IconColor, DragPreviewWidget)
from .action_bindings import KeyCaptureEditor, SneakyDbSpinBox, SneakyTextEditor
from .combo_line_editor import DualMouseEditor
from macro_studio.ui.widgets.standalone.empty_state_widget import EmptyStateWidget

if TYPE_CHECKING:
    from macro_studio.ui.tabs.recorder_tab import RecorderTab

ACTION_BINDINGS = {
    ActionType.KEYBOARD: KeyCaptureEditor,
    ActionType.MOUSE: DualMouseEditor,
    ActionType.DELAY: SneakyDbSpinBox,
    ActionType.TEXT: SneakyTextEditor,
}


class TimelineItemWidget(QWidget):
    """The complex row in the RIGHT timeline."""
    def __init__(self, overlay, mouse_combo_model, data: TimelineStep):
        super().__init__()
        action_type = data.action_type

        self.timeline_data = data
        self.action_type = action_type
        self.partner_item: Union[QListWidgetItem, None] = None

        self.setMouseTracking(True)

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 10, 5)
        self.layout.setSpacing(5)

        # 1. Checkbox: ALWAYS VISIBLE to reserve space
        self.chk_select = QCheckBox()
        self.chk_select.setFixedSize(20, 20)
        self.chk_select.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.chk_select.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # 2. Icon & Text
        self.lbl_icon = createIconLabel(ACTION_TYPES[action_type])

        # Text Logic
        binding = ACTION_BINDINGS.get(action_type)
        if binding is not DualMouseEditor:
            self.action_widget = binding(self, data.value)
        else:
            self.action_widget = DualMouseEditor(self, data.value, overlay, mouse_combo_model)

        container_or_text_lbl = self.action_widget
        if detail:= data.detail:
            container_or_text_lbl = QWidget()
            text_layout = QHBoxLayout()
            text_layout.setContentsMargins(0, 0, 0, 0)
            text_layout.setSpacing(5)
            container_or_text_lbl.setLayout(text_layout)

            arrow_label= createIconLabel("mdi6.tray-arrow-down" if detail == 1 else "mdi6.tray-arrow-up")

            text_layout.addWidget(arrow_label)
            text_layout.addWidget(self.action_widget)

        # 3. Action Buttons (Hidden until hover)
        self.btn_container = QWidget()
        self.btn_layout = QHBoxLayout(self.btn_container)
        self.btn_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_layout.setSpacing(5)

        self.btn_dup = HoverButton("ph.copy", size=28)
        self.btn_dup.icon_hover = createQtIcon("ph.copy-fill")
        self.btn_dup.setToolTip("Duplicate")

        self.btn_del = HoverButton(TRASH_ICON, hover_color="#ff0000", size=28)
        self.btn_del.setToolTip("Delete")

        self.lbl_grip = createIconLabel(GRIP_CONFIG)

        self.btn_layout.addWidget(self.btn_dup)
        self.btn_layout.addWidget(self.btn_del)
        self.btn_layout.addWidget(self.lbl_grip)
        self.btn_container.hide()

        self.layout.addWidget(self.chk_select)
        self.layout.addWidget(self.lbl_icon)
        self.layout.addWidget(container_or_text_lbl)
        self.layout.addStretch()
        self.layout.addWidget(self.btn_container)

        self.is_hovered = False

    def setSelected(self, selected: bool):
        """Public method to update visual state from the parent list."""
        self.chk_select.setChecked(selected)

    def enterEvent(self, event):
        self.is_hovered = True
        self.btn_container.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.btn_container.hide()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.ignore()
        else:
            super().mousePressEvent(event)


class DroppableTimelineWidget(QListWidget):
    """The Timeline List (Right Side)"""

    def __init__(self, recorder_tab: "RecorderTab"):
        super().__init__()
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.is_dragging = False

        self.setObjectName("DroppableTimelineWidget")

        self.setMouseTracking(True)

        # Disable the default indicator (we will draw our own)
        self.setDropIndicatorShown(False)
        self.recorder_tab = recorder_tab

        self._drag_target_row = -1

        self.empty_state = EmptyStateWidget(self.viewport())
        self.empty_state.setupState(
            icon_name="ph.film-strip",
            title="Timeline is empty",
            subtitle="Drag actions from the palette to start building your task"
        )

        # Initial check to see if we should show it
        self.checkEmptyState()

        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._update_dash_offset)
        self.anim_timer.setInterval(40)

        self._dash_offset = 0
        self._active_pair = None  # Tuple: (TimelineItemWidget, TimelineItemWidget)
        self._global_pos = QPoint()

        self.model().rowsInserted.connect(lambda *args: self.checkEmptyState())
        self.model().rowsRemoved.connect(lambda *args: self.checkEmptyState())

    def checkEmptyState(self):
        """Toggles the visibility of the empty state overlay."""
        is_empty = self.count() == 0

        if is_empty:
            # Force it to cover the entire list area
            self.empty_state.resize(self.size())
            self.empty_state.show()
            self.empty_state.raise_()  # Ensure it sits on top of any residual painting
        else:
            self.empty_state.hide()

    def resizeEvent(self, event):
        """Ensure the empty state overlay always fills the widget."""
        super().resizeEvent(event)
        if self.empty_state.isVisible():
            self.empty_state.resize(self.viewport().size())

    def tryLinkWithIdx(self, item_a: QListWidgetItem, widget_a: TimelineItemWidget, other_idx: int):
        """Tries to link the first widget with the item at the other index."""
        if other_idx is None: return
        item_b = self.item(other_idx)
        if not item_b: return
        widget_b = self.itemWidget(item_b)
        widget_a.partner_item = item_b
        widget_b.partner_item = item_a

    def tryUnlinkPartners(self, widget: TimelineItemWidget):
        partner_item = widget.partner_item
        if partner_item:
            widget.partner_item = None
            self.itemWidget(partner_item).partner_item = None

    def tryUpdateHoveredWidget(self):
        global_pos = self._global_pos
        local_pos = self.viewport().mapFromGlobal(global_pos)
        item = self.itemAt(local_pos)
        widget_under_mouse = self.itemWidget(item) if item else None

        if widget_under_mouse:
            child_local_pos = widget_under_mouse.mapFromGlobal(global_pos)

            enter_event = QEnterEvent(
                child_local_pos,
                child_local_pos,  # scene pos (approx)
                global_pos
            )
            QApplication.sendEvent(widget_under_mouse, enter_event)

    def isMoveAllowed(self, target_row):
        """
        Check if moving the selected item(s) to 'target_row' violates
        any partner constraints (e.g. Key Down cannot go below Key Up).
        """
        if self.recorder_tab.palette_drag_action: return True

        for item in self.selectedItems():
            widget = self.itemWidget(item)
            if not widget or not getattr(widget, 'partner_item', None):
                continue

            partner_item = widget.partner_item

            if partner_item.isSelected(): continue  # Partner missing/deleted/selected? Ignore constraint.

            partner_row = self.row(partner_item)
            my_row = self.row(item)

            # "Top" partner cannot be dropped below the "Bottom" partner
            if my_row < partner_row < target_row:
                return False

            # "Bottom" partner cannot be dropped above the "Top" partner
            if my_row > partner_row >= target_row:
                return False

        return True

    def _update_dash_offset(self):
        """Animate the dotted line."""
        self._dash_offset -= 1
        if self._dash_offset < -100: self._dash_offset = 0
        self.viewport().update()

    def _handle_hover_check(self, global_pos):
        """
        Unified logic to find the item under the mouse (passed in Global Coords)
        and check if it has a linked partner.
        """
        if self.is_dragging: return

        viewport_pos = self.viewport().mapFromGlobal(global_pos)
        item = self.itemAt(viewport_pos)

        new_pair = None

        if item:
            widget = self.itemWidget(item)
            if widget and getattr(widget, 'partner_item', None):
                new_pair = (widget, self.itemWidget(widget.partner_item))

        # Only update if the pair has changed
        if self._active_pair != new_pair:
            self._active_pair = new_pair

            if self._active_pair:
                if not self.anim_timer.isActive():
                    self.anim_timer.start()
            else:
                self.anim_timer.stop()

            self.viewport().update()

    def setItemWidget(self, item, widget):
        """
        Overridden to automatically install the Event Filter.
        This lets the List 'see' mouse events occurring on top of this widget.
        """
        super().setItemWidget(item, widget)
        if widget:
            widget.installEventFilter(self)

    def eventFilter(self, source, event):
        """
        Spy on the child widgets to detect mouse movement.
        """
        if event.type() == QEvent.Type.MouseMove:
            # We need Global coordinates to be consistent
            self._global_pos = source.mapToGlobal(event.position().toPoint())
            self._handle_hover_check(self._global_pos)

        return super().eventFilter(source, event)

    def mouseMoveEvent(self, event):
        """
        Handle mouse movement over empty space / margins.
        """
        super().mouseMoveEvent(event)

        # Use Global coordinates to match the eventFilter logic
        global_pos = self.mapToGlobal(event.position().toPoint())
        self._handle_hover_check(global_pos)

    def _clearConnectionLine(self):
        self._active_pair = None
        self.anim_timer.stop()
        self.viewport().update()

    def leaveEvent(self, event):
        """Clear the line immediately when mouse leaves the list area."""
        if not self.is_dragging: self._clearConnectionLine()

        self.anim_timer.stop()
        self.viewport().update()
        super().leaveEvent(event)

    def startDrag(self, supportedActions):
        """Create a custom drag preview for single or multiple items."""
        self.is_dragging = True

        selected_items = self.selectedItems()
        count = len(selected_items)
        if count == 0: return

        text = f"Move {count} action"
        if count > 1:
            config_or_icon = "msc.layers"
            text += "s"
        else:
            config_or_icon = ACTION_TYPES[self.itemWidget(selected_items[0]).action_type]

        preview = DragPreviewWidget(config_or_icon, text)
        preview.adjustSize()
        pixmap = preview.grab()

        drag = QDrag(self)
        drag.setMimeData(self.mimeData(selected_items))
        drag.setPixmap(pixmap)
        drag.setHotSpot(pixmap.rect().center())
        drag.exec(Qt.DropAction.MoveAction)

    def selectionChanged(self, selected: QItemSelection, deselected: QItemSelection):
        """Sync selection state to the custom widget's checkbox."""
        super().selectionChanged(selected, deselected)

        # 1. Handle items that became SELECTED
        for index in selected.indexes():
            item = self.itemFromIndex(index)
            if item and (w := self.itemWidget(item)):
                w.setSelected(True)  # <--- Call our new helper

        # 2. Handle items that became DESELECTED
        for index in deselected.indexes():
            item = self.itemFromIndex(index)
            if item and (w := self.itemWidget(item)):
                w.setSelected(False)  # <--- Call our new helper

    def dragEnterEvent(self, event):
        event.accept()

    def dragMoveEvent(self, event):
        """Calculate row, CHECK CONSTRAINTS, then allow/deny."""
        # 1. Calculate where we WOULD drop
        row = self._calcDropRow(event.position().toPoint())

        # 2. Check if that spot is legal
        if not self.isMoveAllowed(row):
            # INVALID: Hide the line and show 'Forbidden' cursor
            self._drag_target_row = -1
            self.viewport().update()
            event.ignore()
            return

        # 3. VALID: Proceed as normal
        self._drag_target_row = row
        self.viewport().update()
        event.accept()

    def dragLeaveEvent(self, event):
        """Clear the line if drag leaves the widget."""
        self._drag_target_row = -1
        self.viewport().update()
        self.is_dragging = False
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        """Handle the drop using our pre-calculated row."""
        # Get the row we calculated during dragMove
        insert_row = self._calcDropRow(event.position().toPoint())

        if not self.isMoveAllowed(insert_row):
            event.ignore()
            return

        self.is_dragging = False

        # Clear the indicator line
        self._drag_target_row = -1
        self.viewport().update()

        # CASE 1: Internal Move
        if event.source() == self:
            start_row = self.currentRow()
            if start_row != insert_row:
                self.recorder_tab.userMovesStep(insert_row)
            #super().dropEvent(event) Skip super call because recorder will handle the movement
        # CASE 2: External Drop (Palette)
        elif event.mimeData().hasText():
            action_type = self.recorder_tab.palette_drag_action
            self.recorder_tab.palette_drag_action = None
            detail = 1 if ACTION_TYPES[action_type].pairable else None
            self.recorder_tab.userAddsStep(insert_row, TimelineStep(
                action_type=action_type,
                detail=detail,
            ))
            event.accept()
        else:
            event.ignore()

    def _getActivePair(self):
        """
        Returns the active pair only if both widgets in the pair are alive and valid.
        Clears self._active_pair if any are dead.
        """
        active_pair = self._active_pair
        if not active_pair:
            return None

        w1, w2 = active_pair

        # Check 1: Are the Python wrappers None?
        # Check 2: Is the C++ object actually alive? (The critical check)
        if (w1 is None or w2 is None) or (not shiboken6.isValid(w1) or not shiboken6.isValid(w2)):
            self._active_pair = None
            return None

        return active_pair

    def paintEvent(self, event):
        """Draw the list, then draw our custom line on top."""
        super().paintEvent(event)

        painter = QPainter(self.viewport())
        if self._drag_target_row != -1:
            pen = QPen(QColor(IconColor.SELECTED), 2)
            painter.setPen(pen)

            # Determine Y coordinates
            if self.count() == 0:
                y = 0
            elif self._drag_target_row >= self.count():
                # Draw below the last item
                rect = self.visualItemRect(self.item(self.count() - 1))
                y = rect.bottom()
            else:
                # Draw above the target item
                rect = self.visualItemRect(self.item(self._drag_target_row))
                y = rect.top()

            # Draw the line across the full width
            painter.drawLine(0, y, self.width(), y)

        active_pair = self._getActivePair()
        if active_pair is not None:
            w1, w2 = active_pair
            item1 = self.itemAt(w1.pos())
            item2 = self.itemAt(w2.pos())

            if item1 and item2:
                rect1 = self.visualItemRect(item1)
                rect2 = self.visualItemRect(item2)

                if rect1.isValid() and rect2.isValid():
                    self._draw_connection_line(painter, rect1, rect2)

    def _draw_connection_line(self, painter, rect1, rect2):
        # Configuration
        line_color = QColor(IconColor.SELECTED)
        dot_radius = 2

        target_x = rect1.x() + 34

        # Calculate Y positions (Centers of the rows)
        y1 = rect1.center().y()
        y2 = rect2.center().y()

        top_y, bottom_y = min(y1, y2), max(y1, y2)

        # Draw the Dots at endpoints
        painter.setBrush(QBrush(line_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(QPoint(target_x, y1), dot_radius, dot_radius)
        painter.drawEllipse(QPoint(target_x, y2), dot_radius, dot_radius)

        # Draw the Dotted Line
        pen = QPen(line_color)
        pen.setWidth(2)

        # Custom Dash Pattern
        pen.setStyle(Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([4, 4])  # 4px line, 4px space

        pen.setDashOffset(self._dash_offset)

        painter.setPen(pen)
        painter.drawLine(target_x, top_y + dot_radius, target_x, bottom_y - dot_radius)

    def _calcDropRow(self, pos):
        """Helper to find the row index based on mouse Y position."""
        item = self.itemAt(pos)
        if item:
            # Get geometry of hovered item
            rect = self.visualItemRect(item)
            center_y = rect.center().y()

            # If top half, insert before. If bottom half, insert after.
            row = self.row(item)
            if pos.y() > center_y:
                row += 1
            return row
        # If hovering below all items (empty space)
        return self.count()