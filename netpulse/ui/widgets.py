"""Reusable macOS-styled widgets for the NetPulse Dashboard."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class PageScrollArea(QScrollArea):
    """Clean macOS-styled scroll area container for dashboard pages."""

    def __init__(self, inner_widget: QWidget, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWidget(inner_widget)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 4px 2px 4px 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(140, 140, 145, 0.4);
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(140, 140, 145, 0.7);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)


class CardContainer(QFrame):
    """Clean rounded card container matching macOS native aesthetics."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("CardContainer")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            QFrame#CardContainer {
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 8px;
            }
        """)


class MetricCard(CardContainer):
    """Card displaying a labeled metric with value and optional subtext.

    Example:
        CURRENT DOWNLOAD
        ↓ 12.4 MB/s
        Session Peak: 92.3 MB/s
    """

    def __init__(
        self,
        title: str,
        initial_value: str = "0 B/s",
        subtext: str = "",
        value_color: Optional[str] = None,
        prominent: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        # Title / category label
        self._title_label = QLabel(title.upper())
        font_title = QFont()
        font_title.setPointSize(9 if not prominent else 10)
        font_title.setWeight(QFont.Weight.Bold)
        self._title_label.setFont(font_title)
        self._title_label.setStyleSheet("color: #8E8E93; letter-spacing: 0.5px;")
        layout.addWidget(self._title_label)

        # Main prominent value
        self._value_label = QLabel(initial_value)
        font_val = QFont()
        font_val.setPointSize(23 if prominent else 18)
        font_val.setWeight(QFont.Weight.DemiBold if prominent else QFont.Weight.Medium)
        self._value_label.setFont(font_val)
        if value_color:
            self._value_label.setStyleSheet(f"color: {value_color};")
        layout.addWidget(self._value_label)

        # Optional subtext / comparison info
        self._subtext_label = QLabel(subtext)
        font_sub = QFont()
        font_sub.setPointSize(10)
        self._subtext_label.setFont(font_sub)
        self._subtext_label.setStyleSheet("color: #8E8E93;")
        if not subtext:
            self._subtext_label.hide()
        layout.addWidget(self._subtext_label)

    def set_value(self, value: str) -> None:
        """Update main displayed metric value."""
        self._value_label.setText(value)

    update_value = set_value

    def set_subtext(self, subtext: str) -> None:
        """Update secondary subtext."""
        self._subtext_label.setText(subtext)
        if subtext:
            self._subtext_label.show()
        else:
            self._subtext_label.hide()


class StatusIndicator(QWidget):
    """Connection status indicator with a colored status dot."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._label = QLabel("● Connected")
        font_status = QFont()
        font_status.setPointSize(11)
        font_status.setWeight(QFont.Weight.Medium)
        self._label.setFont(font_status)
        self._label.setStyleSheet("color: #4CAF50;")
        layout.addWidget(self._label)

    def set_status(self, status: str) -> None:
        """Update connection status text and color."""
        status_clean = status.strip().lower()
        if "connected" in status_clean:
            color = "#4CAF50"  # Green
            text = "● Connected"
        elif "no network" in status_clean:
            color = "#FF9800"  # Orange
            text = "● No network"
        else:
            color = "#F44336"  # Red
            text = f"● {status}"

        self._label.setText(text)
        self._label.setStyleSheet(f"color: {color};")
