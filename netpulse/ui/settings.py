"""Settings page for the NetPulse Dashboard."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from netpulse.config.models import (
    APPEARANCE_MODE_LABELS,
    DISPLAY_MODE_LABELS,
    INTERVAL_LABELS,
    UNIT_MODE_LABELS,
    AppearanceMode,
    DisplayMode,
    UnitMode,
)
from netpulse.ui.widgets import CardContainer

if TYPE_CHECKING:
    from netpulse.config.preferences import PreferencesManager
    from netpulse.core.network_monitor import NetworkMonitor
    from netpulse.core.reset_coordinator import DataResetCoordinator
    from netpulse.storage.database import Database


class SettingsPage(QWidget):
    """Settings configuration page."""

    def __init__(
        self,
        prefs_manager: PreferencesManager,
        monitor: NetworkMonitor,
        database: Optional[Database] = None,
        reset_coordinator: Optional[DataResetCoordinator] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._prefs = prefs_manager
        self._monitor = monitor
        self._db = database
        self._reset_coordinator = reset_coordinator

        self._setup_ui()
        self.refresh_storage_info()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Settings Card
        card = CardContainer()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 20, 24, 20)
        card_layout.setSpacing(16)

        title = QLabel("PREFERENCES")
        font_title = QFont()
        font_title.setPointSize(11)
        font_title.setWeight(QFont.Weight.Bold)
        title.setFont(font_title)
        title.setStyleSheet("color: gray; letter-spacing: 0.5px;")
        card_layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(14)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        prefs = self._prefs.preferences

        # 0. Start at Login
        self._chk_start_at_login = QCheckBox("Automatically start at login")
        self._chk_start_at_login.setChecked(prefs.start_at_login)
        self._chk_start_at_login.toggled.connect(self._on_start_at_login_toggled)
        form.addRow("", self._chk_start_at_login)

        # 0b. Menu Bar Mascot
        self._chk_mascot = QCheckBox("Enable animated lion")
        self._chk_mascot.setChecked(prefs.enable_mascot)
        self._chk_mascot.toggled.connect(lambda v: self._prefs.update(enable_mascot=v))
        form.addRow("Menu Bar Mascot:", self._chk_mascot)

        # 1. Menu Bar Display Mode
        self._combo_display = QComboBox()
        for mode, label in DISPLAY_MODE_LABELS.items():
            self._combo_display.addItem(label, mode)
            if mode == prefs.display_mode:
                self._combo_display.setCurrentText(label)
        self._combo_display.currentIndexChanged.connect(self._on_display_changed)
        form.addRow("Menu Bar Display:", self._combo_display)

        # 2. Speed Units
        self._combo_units = QComboBox()
        for mode, label in UNIT_MODE_LABELS.items():
            self._combo_units.addItem(label, mode)
            if mode == prefs.unit_mode:
                self._combo_units.setCurrentText(label)
        self._combo_units.currentIndexChanged.connect(self._on_units_changed)
        form.addRow("Speed Unit:", self._combo_units)

        # 3. Refresh Interval
        self._combo_interval = QComboBox()
        for interval, label in INTERVAL_LABELS.items():
            self._combo_interval.addItem(label, interval)
            if interval == prefs.sample_interval:
                self._combo_interval.setCurrentText(label)
        self._combo_interval.currentIndexChanged.connect(self._on_interval_changed)
        form.addRow("Refresh Interval:", self._combo_interval)

        # 4. Appearance Mode
        self._combo_appearance = QComboBox()
        for mode, label in APPEARANCE_MODE_LABELS.items():
            self._combo_appearance.addItem(label, mode)
            if mode == prefs.appearance:
                self._combo_appearance.setCurrentText(label)
        self._combo_appearance.currentIndexChanged.connect(self._on_appearance_changed)
        form.addRow("Appearance:", self._combo_appearance)

        card_layout.addLayout(form)
        layout.addWidget(card)

        # 2. Notifications Card
        notif_card = CardContainer()
        notif_card_layout = QVBoxLayout(notif_card)
        notif_card_layout.setContentsMargins(24, 20, 24, 20)
        notif_card_layout.setSpacing(16)

        notif_title = QLabel("NOTIFICATIONS")
        font_ntitle = QFont()
        font_ntitle.setPointSize(11)
        font_ntitle.setWeight(QFont.Weight.Bold)
        notif_title.setFont(font_ntitle)
        notif_title.setStyleSheet("color: gray; letter-spacing: 0.5px;")
        notif_card_layout.addWidget(notif_title)

        # Master enable toggle
        self._chk_enable_notif = QCheckBox("Enable Native Notifications")
        font_master = QFont()
        font_master.setPointSize(13)
        font_master.setWeight(QFont.Weight.DemiBold)
        self._chk_enable_notif.setFont(font_master)
        self._chk_enable_notif.setChecked(prefs.notifications_enabled)
        self._chk_enable_notif.toggled.connect(self._on_enable_notif_toggled)
        notif_card_layout.addWidget(self._chk_enable_notif)

        # Vertical notification settings container
        notif_items_layout = QVBoxLayout()
        notif_items_layout.setSpacing(14)
        notif_items_layout.setContentsMargins(4, 4, 4, 4)

        # Helper font for subtitles
        font_sub = QFont()
        font_sub.setPointSize(11)

        # A. Network Connection Events
        sec_conn_lbl = QLabel("Connection Events")
        sec_conn_lbl.setStyleSheet("color: gray; font-size: 11px; font-weight: bold; text-transform: uppercase;")
        notif_items_layout.addWidget(sec_conn_lbl)

        self._chk_net_conn = QCheckBox("Notify when connected to a network")
        self._chk_net_conn.setChecked(prefs.notify_network_connected)
        self._chk_net_conn.toggled.connect(lambda v: self._prefs.update(notify_network_connected=v))
        notif_items_layout.addWidget(self._chk_net_conn)

        self._chk_net_disc = QCheckBox("Notify when disconnected from network")
        self._chk_net_disc.setChecked(prefs.notify_network_disconnected)
        self._chk_net_disc.toggled.connect(lambda v: self._prefs.update(notify_network_disconnected=v))
        notif_items_layout.addWidget(self._chk_net_disc)

        self._chk_net_changed = QCheckBox("Notify when network interface or SSID changes")
        self._chk_net_changed.setChecked(prefs.notify_network_changed)
        self._chk_net_changed.toggled.connect(lambda v: self._prefs.update(notify_network_changed=v))
        notif_items_layout.addWidget(self._chk_net_changed)

        self._chk_net_restored = QCheckBox("Notify when connection is restored")
        self._chk_net_restored.setChecked(prefs.notify_connection_restored)
        self._chk_net_restored.toggled.connect(lambda v: self._prefs.update(notify_connection_restored=v))
        notif_items_layout.addWidget(self._chk_net_restored)

        # Separator line
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.HLine)
        sep1.setStyleSheet("color: palette(mid);")
        notif_items_layout.addWidget(sep1)

        # B. Wi-Fi Quality
        sec_wifi_lbl = QLabel("Wi-Fi Quality")
        sec_wifi_lbl.setStyleSheet("color: gray; font-size: 11px; font-weight: bold; text-transform: uppercase;")
        notif_items_layout.addWidget(sec_wifi_lbl)

        wifi_item_layout = QVBoxLayout()
        wifi_item_layout.setSpacing(6)
        self._chk_weak_signal = QCheckBox("Alert on weak Wi-Fi signal")
        self._chk_weak_signal.setChecked(prefs.notify_weak_signal)
        self._chk_weak_signal.toggled.connect(lambda v: self._prefs.update(notify_weak_signal=v))
        wifi_item_layout.addWidget(self._chk_weak_signal)

        rssi_row = QHBoxLayout()
        rssi_row.setContentsMargins(20, 0, 0, 0)
        rssi_row.setSpacing(8)
        lbl_rssi_thresh = QLabel("Signal threshold:")
        lbl_rssi_thresh.setFont(font_sub)
        lbl_rssi_thresh.setStyleSheet("color: gray;")
        self._spin_weak_rssi = QSpinBox()
        self._spin_weak_rssi.setRange(-100, -40)
        self._spin_weak_rssi.setSuffix(" dBm")
        self._spin_weak_rssi.setFixedWidth(110)
        self._spin_weak_rssi.setValue(prefs.weak_signal_rssi_threshold)
        self._spin_weak_rssi.valueChanged.connect(lambda v: self._prefs.update(weak_signal_rssi_threshold=v))
        rssi_row.addWidget(lbl_rssi_thresh)
        rssi_row.addWidget(self._spin_weak_rssi)
        rssi_row.addStretch(1)
        wifi_item_layout.addLayout(rssi_row)
        notif_items_layout.addLayout(wifi_item_layout)

        # Separator line
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("color: palette(mid);")
        notif_items_layout.addWidget(sep2)

        # C. Speed Alerts
        sec_spd_lbl = QLabel("Speed Alerts")
        sec_spd_lbl.setStyleSheet("color: gray; font-size: 11px; font-weight: bold; text-transform: uppercase;")
        notif_items_layout.addWidget(sec_spd_lbl)

        # High download
        dl_item_layout = QVBoxLayout()
        dl_item_layout.setSpacing(6)
        self._chk_high_dl = QCheckBox("Alert on high download activity")
        self._chk_high_dl.setChecked(prefs.notify_high_download_speed)
        self._chk_high_dl.toggled.connect(lambda v: self._prefs.update(notify_high_download_speed=v))
        dl_item_layout.addWidget(self._chk_high_dl)

        dl_row = QHBoxLayout()
        dl_row.setContentsMargins(20, 0, 0, 0)
        dl_row.setSpacing(8)
        lbl_dl_thresh = QLabel("Download speed exceeds:")
        lbl_dl_thresh.setFont(font_sub)
        lbl_dl_thresh.setStyleSheet("color: gray;")
        self._spin_high_dl = QDoubleSpinBox()
        self._spin_high_dl.setRange(1.0, 10000.0)
        self._spin_high_dl.setSuffix(" MB/s")
        self._spin_high_dl.setFixedWidth(110)
        self._spin_high_dl.setValue(prefs.download_speed_threshold_mbps)
        self._spin_high_dl.valueChanged.connect(lambda v: self._prefs.update(download_speed_threshold_mbps=v))
        dl_row.addWidget(lbl_dl_thresh)
        dl_row.addWidget(self._spin_high_dl)
        dl_row.addStretch(1)
        dl_item_layout.addLayout(dl_row)
        notif_items_layout.addLayout(dl_item_layout)

        # High upload
        ul_item_layout = QVBoxLayout()
        ul_item_layout.setSpacing(6)
        self._chk_high_ul = QCheckBox("Alert on high upload activity")
        self._chk_high_ul.setChecked(prefs.notify_high_upload_speed)
        self._chk_high_ul.toggled.connect(lambda v: self._prefs.update(notify_high_upload_speed=v))
        ul_item_layout.addWidget(self._chk_high_ul)

        ul_row = QHBoxLayout()
        ul_row.setContentsMargins(20, 0, 0, 0)
        ul_row.setSpacing(8)
        lbl_ul_thresh = QLabel("Upload speed exceeds:")
        lbl_ul_thresh.setFont(font_sub)
        lbl_ul_thresh.setStyleSheet("color: gray;")
        self._spin_high_ul = QDoubleSpinBox()
        self._spin_high_ul.setRange(1.0, 10000.0)
        self._spin_high_ul.setSuffix(" MB/s")
        self._spin_high_ul.setFixedWidth(110)
        self._spin_high_ul.setValue(prefs.upload_speed_threshold_mbps)
        self._spin_high_ul.valueChanged.connect(lambda v: self._prefs.update(upload_speed_threshold_mbps=v))
        ul_row.addWidget(lbl_ul_thresh)
        ul_row.addWidget(self._spin_high_ul)
        ul_row.addStretch(1)
        ul_item_layout.addLayout(ul_row)
        notif_items_layout.addLayout(ul_item_layout)

        # Separator line
        sep3 = QFrame()
        sep3.setFrameShape(QFrame.Shape.HLine)
        sep3.setStyleSheet("color: palette(mid);")
        notif_items_layout.addWidget(sep3)

        # D. Data Usage Alert
        sec_usage_lbl = QLabel("Data Usage")
        sec_usage_lbl.setStyleSheet("color: gray; font-size: 11px; font-weight: bold; text-transform: uppercase;")
        notif_items_layout.addWidget(sec_usage_lbl)

        usage_item_layout = QVBoxLayout()
        usage_item_layout.setSpacing(6)
        self._chk_high_usage = QCheckBox("Alert on high data usage threshold")
        self._chk_high_usage.setChecked(prefs.notify_high_data_usage)
        self._chk_high_usage.toggled.connect(lambda v: self._prefs.update(notify_high_data_usage=v))
        usage_item_layout.addWidget(self._chk_high_usage)

        usage_row = QHBoxLayout()
        usage_row.setContentsMargins(20, 0, 0, 0)
        usage_row.setSpacing(8)
        lbl_usage_thresh = QLabel("Monthly usage reaches:")
        lbl_usage_thresh.setFont(font_sub)
        lbl_usage_thresh.setStyleSheet("color: gray;")
        self._spin_high_usage = QDoubleSpinBox()
        self._spin_high_usage.setRange(0.5, 1000.0)
        self._spin_high_usage.setSuffix(" GB")
        self._spin_high_usage.setFixedWidth(110)
        self._spin_high_usage.setValue(prefs.data_usage_threshold_gb)
        self._spin_high_usage.valueChanged.connect(lambda v: self._prefs.update(data_usage_threshold_gb=v))
        usage_row.addWidget(lbl_usage_thresh)
        usage_row.addWidget(self._spin_high_usage)
        usage_row.addStretch(1)
        usage_item_layout.addLayout(usage_row)
        notif_items_layout.addLayout(usage_item_layout)

        notif_card_layout.addLayout(notif_items_layout)
        layout.addWidget(notif_card)

        # Data & Storage Card
        data_card = CardContainer()
        data_card_layout = QVBoxLayout(data_card)
        data_card_layout.setContentsMargins(24, 20, 24, 20)
        data_card_layout.setSpacing(14)

        data_title = QLabel("DATA & STORAGE")
        font_dtitle = QFont()
        font_dtitle.setPointSize(11)
        font_dtitle.setWeight(QFont.Weight.Bold)
        data_title.setFont(font_dtitle)
        data_title.setStyleSheet("color: gray; letter-spacing: 0.5px;")
        data_card_layout.addWidget(data_title)

        storage_form = QFormLayout()
        storage_form.setSpacing(10)
        storage_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._lbl_db_path = QLabel("—")
        self._lbl_db_path.setStyleSheet("color: gray; font-size: 11px;")
        self._lbl_db_path.setWordWrap(True)
        storage_form.addRow("Database Location:", self._lbl_db_path)

        self._lbl_db_history = QLabel("—")
        self._lbl_db_history.setStyleSheet("color: gray; font-size: 11px;")
        storage_form.addRow("Stored History:", self._lbl_db_history)

        data_card_layout.addLayout(storage_form)

        # Action Buttons Row
        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)

        self._btn_reset_stats = QPushButton("Reset Statistics & History")
        self._btn_reset_stats.setStyleSheet(
            "QPushButton { background: rgba(255, 149, 0, 0.15); color: #FF9500; "
            "border: 1px solid rgba(255, 149, 0, 0.3); border-radius: 6px; padding: 6px 14px; font-weight: 500; font-size: 12px; }"
            "QPushButton:hover { background: rgba(255, 149, 0, 0.25); }"
        )
        self._btn_reset_stats.clicked.connect(self._on_reset_statistics_clicked)
        actions_row.addWidget(self._btn_reset_stats)

        self._btn_reset_all = QPushButton("Reset All NetPulse Data")
        self._btn_reset_all.setStyleSheet(
            "QPushButton { background: rgba(255, 59, 48, 0.15); color: #FF3B30; "
            "border: 1px solid rgba(255, 59, 48, 0.3); border-radius: 6px; padding: 6px 14px; font-weight: 500; font-size: 12px; }"
            "QPushButton:hover { background: rgba(255, 59, 48, 0.25); }"
        )
        self._btn_reset_all.clicked.connect(self._on_reset_all_clicked)
        actions_row.addWidget(self._btn_reset_all)

        actions_row.addStretch(1)
        data_card_layout.addLayout(actions_row)

        layout.addWidget(data_card)
        layout.addStretch(1)

    def refresh_storage_info(self) -> None:
        """Update storage metadata displayed in the Data & Storage card."""
        if not hasattr(self, "_lbl_db_path"):
            return

        if self._db is None:
            self._lbl_db_path.setText("In-memory database")
            self._lbl_db_history.setText("No persistent storage")
            return

        info = self._db.get_storage_info()
        self._lbl_db_path.setText(str(info["path"]))

        from netpulse.utils.formatters import format_bytes
        size_str = format_bytes(info["size_bytes"])
        if info["has_history"]:
            self._lbl_db_history.setText(
                f"{size_str} ({info['networks_count']} known networks, {info['daily_records_count']} daily records)"
            )
        else:
            self._lbl_db_history.setText(f"{size_str} (No historical records)")

    def reload_preferences_ui(self) -> None:
        """Re-sync all UI controls with current in-memory preferences."""
        prefs = self._prefs.preferences

        # Block signals to avoid firing updates during re-sync
        self._combo_display.blockSignals(True)
        self._combo_units.blockSignals(True)
        self._combo_interval.blockSignals(True)
        self._combo_appearance.blockSignals(True)
        self._chk_start_at_login.blockSignals(True)
        self._chk_mascot.blockSignals(True)
        self._chk_enable_notif.blockSignals(True)
        self._chk_net_conn.blockSignals(True)
        self._chk_net_disc.blockSignals(True)
        self._chk_net_changed.blockSignals(True)
        self._chk_net_restored.blockSignals(True)
        self._chk_weak_signal.blockSignals(True)
        self._spin_weak_rssi.blockSignals(True)
        self._chk_high_dl.blockSignals(True)
        self._spin_high_dl.blockSignals(True)
        self._chk_high_ul.blockSignals(True)
        self._spin_high_ul.blockSignals(True)
        self._chk_high_usage.blockSignals(True)
        self._spin_high_usage.blockSignals(True)

        try:
            self._combo_display.setCurrentText(DISPLAY_MODE_LABELS.get(prefs.display_mode, ""))
            self._combo_units.setCurrentText(UNIT_MODE_LABELS.get(prefs.unit_mode, ""))
            self._combo_interval.setCurrentText(INTERVAL_LABELS.get(prefs.sample_interval, ""))
            self._combo_appearance.setCurrentText(APPEARANCE_MODE_LABELS.get(prefs.appearance, ""))

            self._chk_start_at_login.setChecked(prefs.start_at_login)
            self._chk_mascot.setChecked(prefs.enable_mascot)
            self._chk_enable_notif.setChecked(prefs.notifications_enabled)
            self._chk_net_conn.setChecked(prefs.notify_network_connected)
            self._chk_net_disc.setChecked(prefs.notify_network_disconnected)
            self._chk_net_changed.setChecked(prefs.notify_network_changed)
            self._chk_net_restored.setChecked(prefs.notify_connection_restored)
            self._chk_weak_signal.setChecked(prefs.notify_weak_signal)
            self._spin_weak_rssi.setValue(prefs.weak_signal_rssi_threshold)
            self._chk_high_dl.setChecked(prefs.notify_high_download_speed)
            self._spin_high_dl.setValue(prefs.download_speed_threshold_mbps)
            self._chk_high_ul.setChecked(prefs.notify_high_upload_speed)
            self._spin_high_ul.setValue(prefs.upload_speed_threshold_mbps)
            self._chk_high_usage.setChecked(prefs.notify_high_data_usage)
            self._spin_high_usage.setValue(prefs.data_usage_threshold_gb)
        finally:
            self._combo_display.blockSignals(False)
            self._combo_units.blockSignals(False)
            self._combo_interval.blockSignals(False)
            self._combo_appearance.blockSignals(False)
            self._chk_start_at_login.blockSignals(False)
            self._chk_mascot.blockSignals(False)
            self._chk_enable_notif.blockSignals(False)
            self._chk_net_conn.blockSignals(False)
            self._chk_net_disc.blockSignals(False)
            self._chk_net_changed.blockSignals(False)
            self._chk_net_restored.blockSignals(False)
            self._chk_weak_signal.blockSignals(False)
            self._spin_weak_rssi.blockSignals(False)
            self._chk_high_dl.blockSignals(False)
            self._spin_high_dl.blockSignals(False)
            self._chk_high_ul.blockSignals(False)
            self._spin_high_ul.blockSignals(False)
            self._chk_high_usage.blockSignals(False)
            self._spin_high_usage.blockSignals(False)

    def _on_reset_statistics_clicked(self) -> None:
        """Handle Reset Statistics & History with confirmation dialog."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Reset Statistics & History?")
        msg.setText("Reset Statistics & History?")
        msg.setInformativeText(
            "This will permanently delete your NetPulse network history and statistics. "
            "This action cannot be undone."
        )
        msg.setIcon(QMessageBox.Icon.Warning)
        btn_reset = msg.addButton("Reset History", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(btn_cancel)
        msg.exec()

        if msg.clickedButton() == btn_reset:
            if self._reset_coordinator is not None:
                self._reset_coordinator.reset_statistics_and_history()
            elif self._db is not None:
                self._db.reset_statistics()
            self.refresh_storage_info()

    def _on_reset_all_clicked(self) -> None:
        """Handle Reset All NetPulse Data with confirmation dialog."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Reset All NetPulse Data?")
        msg.setText("Reset All NetPulse Data?")
        msg.setInformativeText(
            "This will permanently delete your NetPulse history, preferences, and settings. "
            "NetPulse will return to its initial state. This action cannot be undone."
        )
        msg.setIcon(QMessageBox.Icon.Warning)
        btn_reset = msg.addButton("Reset Everything", QMessageBox.ButtonRole.DestructiveRole)
        btn_cancel = msg.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        msg.setDefaultButton(btn_cancel)
        msg.exec()

        if msg.clickedButton() == btn_reset:
            if self._reset_coordinator is not None:
                self._reset_coordinator.reset_all_data()
            else:
                if self._db is not None:
                    self._db.reset_statistics()
                self._prefs.reset_to_defaults()
            self.reload_preferences_ui()
            self.refresh_storage_info()

    def _on_start_at_login_toggled(self, enabled: bool) -> None:
        self._prefs.update(start_at_login=enabled)
        from netpulse.platform.login_item import set_login_item_enabled
        set_login_item_enabled(enabled)

    def _on_enable_notif_toggled(self, enabled: bool) -> None:
        self._prefs.update(notifications_enabled=enabled)

    def _on_display_changed(self, index: int) -> None:
        mode = self._combo_display.itemData(index)
        if isinstance(mode, DisplayMode):
            self._prefs.update(display_mode=mode)

    def _on_units_changed(self, index: int) -> None:
        mode = self._combo_units.itemData(index)
        if isinstance(mode, UnitMode):
            self._prefs.update(unit_mode=mode)

    def _on_interval_changed(self, index: int) -> None:
        interval = self._combo_interval.itemData(index)
        if isinstance(interval, (float, int)):
            self._prefs.update(sample_interval=float(interval))
            self._monitor.set_interval(float(interval))

    def _on_appearance_changed(self, index: int) -> None:
        mode = self._combo_appearance.itemData(index)
        if isinstance(mode, AppearanceMode):
            self._prefs.update(appearance=mode)
            from netpulse.ui.theme import apply_appearance_theme
            apply_appearance_theme(mode)
