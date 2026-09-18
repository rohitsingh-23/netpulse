"""macOS theme and appearance management for NetPulse."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from netpulse.config.models import AppearanceMode


def apply_appearance_theme(mode: AppearanceMode) -> None:
    """Apply system, light, or dark theme to the Qt application."""
    app = QApplication.instance()
    if not app:
        return

    if mode == AppearanceMode.SYSTEM:
        # Reset to native default style and palette
        app.setPalette(app.style().standardPalette())
        app.setStyleSheet("")
        return

    if mode == AppearanceMode.DARK:
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(30, 30, 30))
        dark_palette.setColor(QPalette.ColorRole.WindowText, QColor(240, 240, 240))
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(38, 38, 38))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(48, 48, 48))
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        dark_palette.setColor(QPalette.ColorRole.Text, QColor(240, 240, 240))
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(45, 45, 45))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, QColor(240, 240, 240))
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        dark_palette.setColor(QPalette.ColorRole.Link, QColor(10, 132, 255))
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(10, 132, 255))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Mid, QColor(60, 60, 60))
        app.setPalette(dark_palette)
        app.setStyleSheet("""
            QWidget {
                color: #F0F0F0;
            }
            QPushButton {
                background-color: #3A3A3C;
                border: 1px solid #48484A;
                border-radius: 6px;
                padding: 5px 12px;
                color: #FFFFFF;
            }
            QPushButton:checked {
                background-color: #0A84FF;
                border-color: #0A84FF;
                color: #FFFFFF;
            }
            QComboBox {
                background-color: #3A3A3C;
                border: 1px solid #48484A;
                border-radius: 6px;
                padding: 4px 10px;
                color: #FFFFFF;
            }
            QListWidget {
                background-color: #242426;
                border: none;
            }
        """)
        return

    if mode == AppearanceMode.LIGHT:
        light_palette = QPalette()
        light_palette.setColor(QPalette.ColorRole.Window, QColor(245, 245, 247))
        light_palette.setColor(QPalette.ColorRole.WindowText, QColor(29, 29, 31))
        light_palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        light_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(242, 242, 247))
        light_palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 255))
        light_palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
        light_palette.setColor(QPalette.ColorRole.Text, QColor(29, 29, 31))
        light_palette.setColor(QPalette.ColorRole.Button, QColor(255, 255, 255))
        light_palette.setColor(QPalette.ColorRole.ButtonText, QColor(29, 29, 31))
        light_palette.setColor(QPalette.ColorRole.Link, QColor(0, 122, 255))
        light_palette.setColor(QPalette.ColorRole.Highlight, QColor(0, 122, 255))
        light_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)
        light_palette.setColor(QPalette.ColorRole.Mid, QColor(219, 219, 224))
        app.setPalette(light_palette)
        app.setStyleSheet("""
            QWidget {
                color: #1D1D1F;
            }
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                padding: 5px 12px;
                color: #1D1D1F;
            }
            QPushButton:checked {
                background-color: #007AFF;
                border-color: #007AFF;
                color: #FFFFFF;
            }
            QComboBox {
                background-color: #FFFFFF;
                border: 1px solid #D1D1D6;
                border-radius: 6px;
                padding: 4px 10px;
                color: #1D1D1F;
            }
            QListWidget {
                background-color: #F2F2F7;
                border: none;
            }
        """)
