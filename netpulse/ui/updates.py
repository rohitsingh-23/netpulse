"""Updates dashboard page for viewing version info, release notes, and checking for updates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, QThread, QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from netpulse.ui.widgets import CardContainer
from netpulse.updates.models import ReleaseNote, UpdateStatus
from netpulse.updates.service import UpdateService
from netpulse.utils.constants import APP_NAME, APP_VERSION, GITHUB_LATEST_RELEASE_URL

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager


class _UpdateWorker(QObject):
    """Background worker for non-blocking update checking."""

    finished = Signal(object, object, str)  # status, release_note, message

    def __init__(self, service: UpdateService) -> None:
        super().__init__()
        self._service = service

    def run(self) -> None:
        status, release, msg = self._service.check_for_updates()
        self.finished.emit(status, release, msg)


class UpdatesPage(QWidget):
    """Updates and Release Notes page in the NetPulse Dashboard."""

    def __init__(
        self,
        prefs_manager: PreferencesManager,
        service: Optional[UpdateService] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._prefs = prefs_manager
        self._service = service or UpdateService()
        self._worker_thread: Optional[QThread] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Header Card with Check for Updates action
        header_card = CardContainer()
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(20, 18, 20, 18)
        header_layout.setSpacing(12)

        header_row = QHBoxLayout()
        header_col = QVBoxLayout()
        header_col.setSpacing(4)

        title = QLabel("Updates")
        font_title = QFont()
        font_title.setPointSize(20)
        font_title.setWeight(QFont.Weight.Bold)
        title.setFont(font_title)

        subtitle = QLabel("View current version status and release history.")
        subtitle.setStyleSheet("color: gray; font-size: 13px;")

        header_col.addWidget(title)
        header_col.addWidget(subtitle)
        header_row.addLayout(header_col)
        header_row.addStretch(1)

        # Check for Updates Button
        self._check_btn = QPushButton("Check for Updates")
        self._check_btn.setFixedWidth(160)
        self._check_btn.setFixedHeight(34)
        self._check_btn.setStyleSheet("""
            QPushButton {
                background-color: palette(highlight);
                color: palette(highlighted-text);
                font-weight: 600;
                border-radius: 6px;
                padding: 6px 14px;
            }
            QPushButton:hover {
                opacity: 0.9;
            }
            QPushButton:disabled {
                background-color: rgba(140, 140, 145, 0.3);
                color: gray;
            }
        """)
        self._check_btn.clicked.connect(self._on_check_clicked)
        header_row.addWidget(self._check_btn)

        header_layout.addLayout(header_row)

        # Status badge / line
        status_row = QHBoxLayout()
        self._status_label = QLabel(f"You're running the latest version (v{APP_VERSION}).")
        font_status = QFont()
        font_status.setPointSize(13)
        self._status_label.setFont(font_status)
        self._status_label.setStyleSheet("color: #34C759; font-weight: 500;")
        status_row.addWidget(self._status_label)
        status_row.addStretch(1)

        # View Release Button (hidden unless an update or remote release is present)
        self._view_release_btn = QPushButton("View Release")
        self._view_release_btn.setFixedWidth(130)
        self._view_release_btn.setFixedHeight(30)
        self._view_release_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: palette(highlight);
                border: 1px solid palette(highlight);
                font-weight: 600;
                border-radius: 6px;
                padding: 4px 10px;
            }
            QPushButton:hover {
                background-color: rgba(0, 122, 255, 0.1);
            }
        """)
        self._view_release_btn.clicked.connect(self._on_view_release_clicked)
        self._view_release_btn.setVisible(False)
        self._current_release_url: str = GITHUB_LATEST_RELEASE_URL
        status_row.addWidget(self._view_release_btn)

        header_layout.addLayout(status_row)

        # Discovered update banner card (hidden by default)
        self._update_banner = CardContainer()
        self._update_banner_layout = QVBoxLayout(self._update_banner)
        self._update_banner_layout.setContentsMargins(20, 16, 20, 16)
        self._update_banner_layout.setSpacing(8)

        self._banner_title = QLabel("New Version Available")
        font_bt = QFont()
        font_bt.setPointSize(14)
        font_bt.setWeight(QFont.Weight.Bold)
        self._banner_title.setFont(font_bt)
        self._banner_title.setStyleSheet("color: #007AFF;")
        self._update_banner_layout.addWidget(self._banner_title)

        self._banner_desc = QLabel()
        self._banner_desc.setWordWrap(True)
        self._banner_desc.setStyleSheet("color: palette(text); line-height: 1.4;")
        self._update_banner_layout.addWidget(self._banner_desc)

        self._update_banner.setVisible(False)
        header_layout.addWidget(self._update_banner)

        layout.addWidget(header_card)

        # 2. Current Release Card (What's New)
        releases = self._service.get_local_releases()
        current_release = releases[0] if releases else None

        if current_release:
            release_card = CardContainer()
            release_layout = QVBoxLayout(release_card)
            release_layout.setContentsMargins(22, 18, 22, 18)
            release_layout.setSpacing(14)

            # Section label
            lbl_hdr = QLabel("WHAT'S NEW IN THIS VERSION")
            font_hdr = QFont()
            font_hdr.setPointSize(11)
            font_hdr.setWeight(QFont.Weight.Bold)
            lbl_hdr.setFont(font_hdr)
            lbl_hdr.setStyleSheet("color: gray; letter-spacing: 0.5px;")
            release_layout.addWidget(lbl_hdr)

            # Release title + date
            title_box = QHBoxLayout()
            ver_title = QLabel(f"{APP_NAME} {current_release.version}")
            font_v = QFont()
            font_v.setPointSize(15)
            font_v.setWeight(QFont.Weight.Bold)
            ver_title.setFont(font_v)

            date_lbl = QLabel(current_release.release_date)
            date_lbl.setStyleSheet("color: gray; font-size: 13px;")

            title_box.addWidget(ver_title)
            title_box.addStretch(1)
            title_box.addWidget(date_lbl)
            release_layout.addLayout(title_box)

            # Summary
            summary_lbl = QLabel(current_release.summary)
            summary_lbl.setStyleSheet("color: palette(text); font-size: 13px;")
            summary_lbl.setWordWrap(True)
            release_layout.addWidget(summary_lbl)

            # Features list
            for feat in current_release.features:
                feat_box = QVBoxLayout()
                feat_box.setSpacing(2)

                feat_title = QLabel(f"• {feat.title}")
                f_font = QFont()
                f_font.setPointSize(13)
                f_font.setWeight(QFont.Weight.DemiBold)
                feat_title.setFont(f_font)

                feat_desc = QLabel(feat.description)
                feat_desc.setStyleSheet("color: palette(text); margin-left: 12px;")
                feat_desc.setWordWrap(True)

                feat_box.addWidget(feat_title)
                feat_box.addWidget(feat_desc)
                release_layout.addLayout(feat_box)

            layout.addWidget(release_card)

        # 3. Release History Card
        history_card = CardContainer()
        hist_layout = QVBoxLayout(history_card)
        hist_layout.setContentsMargins(22, 18, 22, 18)
        hist_layout.setSpacing(10)

        lbl_hist = QLabel("RELEASE HISTORY")
        font_h = QFont()
        font_h.setPointSize(11)
        font_h.setWeight(QFont.Weight.Bold)
        lbl_hist.setFont(font_h)
        lbl_hist.setStyleSheet("color: gray; letter-spacing: 0.5px;")
        hist_layout.addWidget(lbl_hist)

        for rel in releases:
            row = QHBoxLayout()
            ver_lbl = QLabel(f"Version {rel.version}")
            v_font = QFont()
            v_font.setPointSize(13)
            v_font.setWeight(QFont.Weight.Medium)
            ver_lbl.setFont(v_font)

            rel_date = QLabel(rel.release_date)
            rel_date.setStyleSheet("color: gray; font-size: 12px;")

            row.addWidget(ver_lbl)
            row.addStretch(1)
            row.addWidget(rel_date)
            hist_layout.addLayout(row)

        layout.addWidget(history_card)

    def _on_check_clicked(self) -> None:
        """Handle explicit check for updates click."""
        self._check_btn.setEnabled(False)
        self._check_btn.setText("Checking...")
        self._status_label.setStyleSheet("color: gray; font-weight: 500;")
        self._status_label.setText("Checking for updates...")

        self._worker_thread = QThread()
        self._worker = _UpdateWorker(self._service)
        self._worker.moveToThread(self._worker_thread)

        self._worker_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_check_finished)
        self._worker.finished.connect(self._worker_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker_thread.finished.connect(self._worker_thread.deleteLater)

        self._worker_thread.start()

    def _on_view_release_clicked(self) -> None:
        """Open the official release URL in default browser."""
        url = getattr(self, "_current_release_url", GITHUB_LATEST_RELEASE_URL)
        QDesktopServices.openUrl(QUrl(url))

    def _on_check_finished(
        self,
        status: UpdateStatus,
        release: Optional[ReleaseNote],
        message: str,
    ) -> None:
        """Process check result on main thread."""
        self._check_btn.setEnabled(True)
        self._check_btn.setText("Check for Updates")

        if status == UpdateStatus.UP_TO_DATE:
            self._status_label.setStyleSheet("color: #34C759; font-weight: 500;")
            self._status_label.setText(message)
            self._update_banner.setVisible(False)
            self._view_release_btn.setVisible(False)
        elif status == UpdateStatus.UPDATE_AVAILABLE:
            self._status_label.setStyleSheet("color: #007AFF; font-weight: 600;")
            self._status_label.setText(message)
            if release:
                self._current_release_url = release.download_url or GITHUB_LATEST_RELEASE_URL
                self._banner_title.setText(f"NetPulse v{release.version} Available")
                details_text = f"<b>Release Date:</b> {release.release_date or 'Recent'}<br><br>{release.summary}"
                self._banner_desc.setText(details_text)
                self._update_banner.setVisible(True)
                self._view_release_btn.setVisible(True)
        elif status == UpdateStatus.NOT_CONFIGURED:
            self._status_label.setStyleSheet("color: gray; font-weight: 500;")
            self._status_label.setText("Release information is not available yet.")
            self._update_banner.setVisible(False)
            self._view_release_btn.setVisible(False)
        else:
            self._status_label.setStyleSheet("color: #FF3B30; font-weight: 500;")
            self._status_label.setText(message)
            self._update_banner.setVisible(False)
            self._view_release_btn.setVisible(False)
