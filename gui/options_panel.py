"""オプションパネル (PySide6)"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QCheckBox,
    QSlider, QLabel, QPushButton, QProgressBar, QFrame,
)

from core.i18n import tr


class OptionsPanel(QWidget):
    """逆再生/ループ/クロップ + 品質 + GIF/MP4出力 + プログレス"""

    save_gif = Signal()
    save_mp4 = Signal()
    cancel = Signal()
    crop_toggled = Signal(bool)
    open_folder = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # セパレーター
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background-color: #333333;")
        main_layout.addWidget(sep)

        # コンテンツ
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 8, 12, 8)
        content_layout.setSpacing(4)
        self._content = content

        # チェックボックス行
        checks = QWidget()
        checks_layout = QHBoxLayout(checks)
        checks_layout.setContentsMargins(0, 0, 0, 0)

        self.cb_reverse = QCheckBox(tr("cb_reverse"))
        self.cb_reverse.stateChanged.connect(self._on_reverse_changed)
        checks_layout.addWidget(self.cb_reverse)

        self.cb_boomerang = QCheckBox(tr("cb_boomerang"))
        self.cb_boomerang.stateChanged.connect(self._on_boomerang_changed)
        checks_layout.addWidget(self.cb_boomerang)

        self.cb_crop = QCheckBox(tr("cb_crop"))
        self.cb_crop.stateChanged.connect(self._on_crop_changed)
        checks_layout.addWidget(self.cb_crop)

        checks_layout.addStretch()
        content_layout.addWidget(checks)

        # 品質スライダー行
        quality_row = QWidget()
        quality_layout = QHBoxLayout(quality_row)
        quality_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_quality_label = QLabel(tr("label_quality"))
        quality_layout.addWidget(self.lbl_quality_label)

        self.lbl_low = QLabel(tr("label_low"))
        self.lbl_low.setStyleSheet("color: #888888; font-size: 9pt;")
        quality_layout.addWidget(self.lbl_low)

        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(1, 28)
        self.quality_slider.setValue(18)
        self.quality_slider.setInvertedAppearance(True)
        self.quality_slider.setFixedWidth(200)
        self.quality_slider.valueChanged.connect(self._on_quality_changed)
        quality_layout.addWidget(self.quality_slider)

        self.lbl_high = QLabel(tr("label_high"))
        self.lbl_high.setStyleSheet("color: #888888; font-size: 9pt;")
        quality_layout.addWidget(self.lbl_high)

        self.lbl_quality = QLabel("CRF 18")
        self.lbl_quality.setStyleSheet("color: #888888; font-family: Consolas; font-size: 9pt;")
        quality_layout.addWidget(self.lbl_quality)

        quality_layout.addStretch()
        content_layout.addWidget(quality_row)

        # 出力ボタン行
        save_row = QWidget()
        save_layout = QHBoxLayout(save_row)
        save_layout.setContentsMargins(0, 8, 0, 0)

        self.btn_save_gif = QPushButton(tr("btn_save_gif"))
        self.btn_save_gif.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: #ffffff; border: none;
                          font-size: 12pt; font-weight: bold; padding: 6px 20px; }
            QPushButton:hover { background-color: #388E3C; }
            QPushButton:disabled { background-color: #2a2a2a; color: #666666; }
        """)
        self.btn_save_gif.clicked.connect(self.save_gif.emit)
        save_layout.addWidget(self.btn_save_gif)

        self.btn_save_mp4 = QPushButton(tr("btn_save_mp4"))
        self.btn_save_mp4.setStyleSheet("""
            QPushButton { background-color: #2196F3; color: #ffffff; border: none;
                          font-size: 12pt; font-weight: bold; padding: 6px 20px; }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #2a2a2a; color: #666666; }
        """)
        self.btn_save_mp4.clicked.connect(self.save_mp4.emit)
        save_layout.addWidget(self.btn_save_mp4)

        self.btn_open_folder = QPushButton(tr("btn_open_folder"))
        self.btn_open_folder.setStyleSheet("""
            QPushButton { background-color: #333333; color: #ffffff; border: none;
                          font-size: 10pt; padding: 4px 12px; }
            QPushButton:hover { background-color: #444444; }
        """)
        self.btn_open_folder.clicked.connect(self.open_folder.emit)
        self.btn_open_folder.hide()
        save_layout.addWidget(self.btn_open_folder)

        save_layout.addStretch()
        content_layout.addWidget(save_row)

        # プログレスバー行（初期非表示）
        self.progress_frame = QWidget()
        progress_layout = QHBoxLayout(self.progress_frame)
        progress_layout.setContentsMargins(0, 8, 0, 0)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar, stretch=1)

        self.lbl_progress = QLabel("0%")
        self.lbl_progress.setStyleSheet("color: #ffffff; font-family: Consolas; font-size: 10pt;")
        progress_layout.addWidget(self.lbl_progress)

        self.btn_cancel = QPushButton(tr("btn_cancel"))
        self.btn_cancel.setStyleSheet("""
            QPushButton { background-color: #D32F2F; color: #ffffff; border: none;
                          font-size: 9pt; padding: 2px 8px; }
            QPushButton:hover { background-color: #B71C1C; }
        """)
        self.btn_cancel.clicked.connect(self.cancel.emit)
        progress_layout.addWidget(self.btn_cancel)

        self.progress_frame.hide()
        content_layout.addWidget(self.progress_frame)

        # ライセンス状態ラベル
        self.lbl_license = QLabel("")
        self.lbl_license.setStyleSheet("color: #888888; font-size: 9pt;")
        content_layout.addWidget(self.lbl_license)

        # 出力パスラベル（初期非表示）
        self.lbl_output = QLabel("")
        self.lbl_output.setStyleSheet("color: #888888; font-size: 9pt;")
        self.lbl_output.hide()
        content_layout.addWidget(self.lbl_output)

        main_layout.addWidget(content)

    # ===== 内部コールバック =====

    def _on_reverse_changed(self, state):
        if state == Qt.CheckState.Checked.value:
            self.cb_boomerang.setChecked(False)

    def _on_boomerang_changed(self, state):
        if state == Qt.CheckState.Checked.value:
            self.cb_reverse.setChecked(False)

    def _on_crop_changed(self, state):
        self.crop_toggled.emit(state == Qt.CheckState.Checked.value)

    def _on_quality_changed(self, value):
        self.lbl_quality.setText(f"CRF {value}")

    # ===== プロパティ =====

    @property
    def reverse(self) -> bool:
        return self.cb_reverse.isChecked()

    @property
    def boomerang(self) -> bool:
        return self.cb_boomerang.isChecked()

    @property
    def crop_enabled(self) -> bool:
        return self.cb_crop.isChecked()

    @property
    def quality(self) -> int:
        return self.quality_slider.value()

    # ===== 外部API =====

    def show_progress(self):
        self.progress_frame.show()
        self.progress_bar.setValue(0)
        self.lbl_progress.setText("0%")
        self.btn_save_gif.setEnabled(False)
        self.btn_save_mp4.setEnabled(False)

    def update_progress(self, ratio: float):
        pct = int(ratio * 100)
        self.progress_bar.setValue(pct)
        self.lbl_progress.setText(f"{pct}%")

    def hide_progress(self):
        self.progress_frame.hide()
        self.btn_save_gif.setEnabled(True)
        self.btn_save_mp4.setEnabled(True)

    def show_output_path(self, path: str):
        self.lbl_output.setText(tr("label_output", path=path))
        self.lbl_output.show()
        self.btn_open_folder.show()

    def set_enabled(self, enabled: bool):
        self.cb_reverse.setEnabled(enabled)
        self.cb_boomerang.setEnabled(enabled)
        self.cb_crop.setEnabled(enabled)
        self.quality_slider.setEnabled(enabled)
        self.btn_save_gif.setEnabled(enabled)
        self.btn_save_mp4.setEnabled(enabled)

    def set_license_status(self, licensed: bool):
        self._licensed = licensed
        if licensed:
            self.lbl_license.setText(tr("license_active"))
            self.lbl_license.setStyleSheet("color: #4CAF50; font-size: 9pt;")
        else:
            self.lbl_license.setText(tr("license_free"))
            self.lbl_license.setStyleSheet("color: #FF9800; font-size: 9pt;")

    def retranslate(self):
        self.cb_reverse.setText(tr("cb_reverse"))
        self.cb_boomerang.setText(tr("cb_boomerang"))
        self.cb_crop.setText(tr("cb_crop"))
        self.lbl_quality_label.setText(tr("label_quality"))
        self.lbl_low.setText(tr("label_low"))
        self.lbl_high.setText(tr("label_high"))
        self.btn_save_gif.setText(tr("btn_save_gif"))
        self.btn_save_mp4.setText(tr("btn_save_mp4"))
        self.btn_open_folder.setText(tr("btn_open_folder"))
        self.btn_cancel.setText(tr("btn_cancel"))
        self.set_license_status(self._licensed)
