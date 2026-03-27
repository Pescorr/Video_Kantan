"""動画プレイヤーウィジェット (PySide6)"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QFont, QImage, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider

from PIL import Image

from core.i18n import tr
from gui.seekbar_widget import SeekBarWidget


class ClickableTimeLabel(QLabel):
    """クリック可能な時刻ラベル"""
    clicked = Signal()

    _STYLE_NORMAL = "color: #2196F3; font-family: Consolas; font-size: 10pt;"
    _STYLE_HOVER = "color: #64B5F6; font-family: Consolas; font-size: 10pt; text-decoration: underline;"

    def __init__(self, text="00:00.000", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(self._STYLE_NORMAL)

    def enterEvent(self, event):
        self.setStyleSheet(self._STYLE_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setStyleSheet(self._STYLE_NORMAL)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class VideoDisplay(QWidget):
    """QPainterベースの動画表示ウィジェット"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: #000000;")
        self.setMinimumSize(100, 100)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._current_pixmap: QPixmap | None = None
        self._placeholder_visible = True

    def display_frame(self, image: Image.Image):
        self._placeholder_visible = False
        if image.mode != "RGB":
            image = image.convert("RGB")
        data = image.tobytes("raw", "RGB")
        qimg = QImage(data, image.width, image.height,
                      image.width * 3, QImage.Format.Format_RGB888)
        self._current_pixmap = QPixmap.fromImage(qimg)
        self.update()

    def get_display_rect(self) -> tuple[int, int, int, int]:
        """動画の実際の表示領域 (x, y, w, h) を返す"""
        if not self._current_pixmap:
            return (0, 0, self.width(), self.height())
        pw, ph = self._current_pixmap.width(), self._current_pixmap.height()
        w, h = self.width(), self.height()
        scale = min(w / pw, h / ph)
        tw, th = int(pw * scale), int(ph * scale)
        ox, oy = (w - tw) // 2, (h - th) // 2
        return (ox, oy, tw, th)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0))

        if self._placeholder_visible:
            p.setPen(QColor("#666666"))
            p.setFont(QFont("", 14))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                       tr("placeholder_drag"))
        elif self._current_pixmap:
            pw, ph = self._current_pixmap.width(), self._current_pixmap.height()
            w, h = self.width(), self.height()
            scale = min(w / pw, h / ph)
            tw, th = int(pw * scale), int(ph * scale)
            ox, oy = (w - tw) // 2, (h - th) // 2
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawPixmap(ox, oy, tw, th, self._current_pixmap)

        p.end()


class PlayerWidget(QWidget):
    """Omnigif風の動画プレイヤー"""

    play_pause = Signal()
    seek = Signal(float)
    prev_frame = Signal()
    next_frame = Signal()
    goto_a = Signal()
    goto_b = Signal()
    set_a_to_current = Signal()
    set_b_to_current = Signal()
    audio_toggled = Signal(bool)
    audiostretch_toggled = Signal(bool)
    speed_changed = Signal(float)
    playback_mode_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_playing = False
        self._audio_on = False
        self._audiostretch_on = False
        self._duration = 0.0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 動画表示
        self.video_display = VideoDisplay()
        layout.addWidget(self.video_display, stretch=1)

        # コントロール行
        controls = QWidget()
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(8, 4, 8, 0)

        btn_style = """
            QPushButton {
                background-color: #333333; color: #ffffff;
                border: none; font-size: 12pt;
                padding: 2px 4px; min-width: 32px;
            }
            QPushButton:hover { background-color: #444444; }
        """
        play_style = """
            QPushButton {
                background-color: #333333; color: #ffffff;
                border: none; font-size: 12pt;
                padding: 2px 4px; min-width: 42px;
            }
            QPushButton:hover { background-color: #444444; }
        """

        # ボタン群
        btn_frame = QWidget()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(2)

        self.btn_goto_a = QPushButton("|◄")
        self.btn_goto_a.setStyleSheet(btn_style)
        self.btn_goto_a.clicked.connect(self.goto_a.emit)
        btn_layout.addWidget(self.btn_goto_a)

        self.btn_prev = QPushButton("◄")
        self.btn_prev.setStyleSheet(btn_style)
        self.btn_prev.clicked.connect(self.prev_frame.emit)
        btn_layout.addWidget(self.btn_prev)

        self.btn_play = QPushButton("▶")
        self.btn_play.setStyleSheet(play_style)
        self.btn_play.clicked.connect(self.play_pause.emit)
        btn_layout.addWidget(self.btn_play)

        self.btn_next = QPushButton("►")
        self.btn_next.setStyleSheet(btn_style)
        self.btn_next.clicked.connect(self.next_frame.emit)
        btn_layout.addWidget(self.btn_next)

        self.btn_goto_b = QPushButton("►|")
        self.btn_goto_b.setStyleSheet(btn_style)
        self.btn_goto_b.clicked.connect(self.goto_b.emit)
        btn_layout.addWidget(self.btn_goto_b)

        self.btn_audio = QPushButton("🔇")
        self.btn_audio.setStyleSheet(btn_style)
        self.btn_audio.setToolTip(tr("tooltip_audio_off"))
        self.btn_audio.clicked.connect(self._on_audio_clicked)
        btn_layout.addWidget(self.btn_audio)

        self._btn_style_normal = btn_style
        self.btn_audiostretch = QPushButton("🎵")
        self.btn_audiostretch.setStyleSheet(btn_style)
        self.btn_audiostretch.setToolTip(tr("tooltip_audiostretch_off"))
        self.btn_audiostretch.clicked.connect(self._on_audiostretch_clicked)
        self.btn_audiostretch.setEnabled(False)
        btn_layout.addWidget(self.btn_audiostretch)

        # 速度コントロール
        btn_layout.addSpacing(8)

        self.lbl_speed = QLabel("x1.00")
        self.lbl_speed.setStyleSheet(
            "color: #ffffff; font-family: Consolas; font-size: 9pt; min-width: 38px;"
        )
        self.lbl_speed.setCursor(Qt.CursorShape.PointingHandCursor)
        self.lbl_speed.setToolTip(tr("tooltip_speed"))
        self.lbl_speed.mouseDoubleClickEvent = lambda e: self._reset_speed()
        btn_layout.addWidget(self.lbl_speed)

        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(10, 300)
        self.slider_speed.setValue(100)
        self.slider_speed.setSingleStep(5)
        self.slider_speed.setFixedWidth(100)
        self.slider_speed.valueChanged.connect(self._on_speed_changed)
        btn_layout.addWidget(self.slider_speed)

        # 再生モードボタン
        btn_layout.addSpacing(8)

        self._mode_active_style = (
            "QPushButton { background-color: #2196F3; color: #ffffff; "
            "border: none; font-size: 12pt; padding: 2px 4px; min-width: 32px; }"
            "QPushButton:hover { background-color: #1976D2; }"
        )

        self.btn_reverse = QPushButton("◄◄")
        self.btn_reverse.setStyleSheet(btn_style)
        self.btn_reverse.setToolTip(tr("tooltip_reverse"))
        self.btn_reverse.setCheckable(True)
        self.btn_reverse.clicked.connect(self._on_reverse_clicked)
        btn_layout.addWidget(self.btn_reverse)

        self.btn_boomerang = QPushButton("◄►")
        self.btn_boomerang.setStyleSheet(btn_style)
        self.btn_boomerang.setToolTip(tr("tooltip_boomerang"))
        self.btn_boomerang.setCheckable(True)
        self.btn_boomerang.clicked.connect(self._on_boomerang_clicked)
        btn_layout.addWidget(self.btn_boomerang)

        controls_layout.addWidget(btn_frame)
        controls_layout.addStretch()

        # 時刻ラベル群
        info_frame = QWidget()
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(0)

        self.lbl_current = QLabel("00:00.000")
        self.lbl_current.setStyleSheet("color: #ffffff; font-family: Consolas; font-size: 10pt;")
        info_layout.addWidget(self.lbl_current)

        spacer = QLabel("    ")
        spacer.setStyleSheet("color: #888888;")
        info_layout.addWidget(spacer)

        self.lbl_a_time = ClickableTimeLabel("00:00.000")
        self.lbl_a_time.clicked.connect(self.set_a_to_current.emit)
        info_layout.addWidget(self.lbl_a_time)

        arrow_label = QLabel(" ←→ ")
        arrow_label.setStyleSheet("color: #888888; font-size: 10pt;")
        info_layout.addWidget(arrow_label)

        self.lbl_b_time = ClickableTimeLabel("00:00.000")
        self.lbl_b_time.clicked.connect(self.set_b_to_current.emit)
        info_layout.addWidget(self.lbl_b_time)

        controls_layout.addWidget(info_frame)
        layout.addWidget(controls)

        # シークバー
        self.seekbar = SeekBarWidget()
        self.seekbar.seeked.connect(self.seek.emit)
        seekbar_container = QWidget()
        seekbar_layout = QHBoxLayout(seekbar_container)
        seekbar_layout.setContentsMargins(8, 2, 8, 8)
        seekbar_layout.addWidget(self.seekbar)
        layout.addWidget(seekbar_container)

    def set_duration(self, duration: float):
        self._duration = duration
        self.seekbar.set_duration(duration)
        self.lbl_b_time.setText(self._format_time(duration))

    def display_frame(self, image: Image.Image, timestamp: float = 0.0):
        self.video_display.display_frame(image)
        self.seekbar.set_head_position(timestamp)
        self.lbl_current.setText(self._format_time(timestamp))

    def update_play_state(self, is_playing: bool):
        self._is_playing = is_playing
        self.btn_play.setText("⏸" if is_playing else "▶")

    def update_ab_labels(self, a_time: float, b_time: float):
        self.lbl_a_time.setText(self._format_time(a_time))
        self.lbl_b_time.setText(self._format_time(b_time))

    def _on_audio_clicked(self):
        self._audio_on = not self._audio_on
        self._update_audio_button()
        self.audio_toggled.emit(self._audio_on)

    def _update_audio_button(self):
        if self._audio_on:
            self.btn_audio.setText("🔊")
            self.btn_audio.setToolTip(tr("tooltip_audio_on"))
        else:
            self.btn_audio.setText("🔇")
            self.btn_audio.setToolTip(tr("tooltip_audio_off"))

    def _on_audiostretch_clicked(self):
        self._audiostretch_on = not self._audiostretch_on
        self._update_audiostretch_button()
        self.audiostretch_toggled.emit(self._audiostretch_on)

    def _update_audiostretch_button(self):
        if self._audiostretch_on:
            self.btn_audiostretch.setText("🎵")
            self.btn_audiostretch.setStyleSheet(
                "QPushButton { background-color: #2196F3; color: #ffffff; "
                "border: none; font-size: 12pt; padding: 2px 4px; min-width: 32px; }"
                "QPushButton:hover { background-color: #1976D2; }"
            )
            self.btn_audiostretch.setToolTip(tr("tooltip_audiostretch_on"))
        else:
            self.btn_audiostretch.setText("🎵")
            self.btn_audiostretch.setStyleSheet(self._btn_style_normal)
            self.btn_audiostretch.setToolTip(tr("tooltip_audiostretch_off"))

    def _on_speed_changed(self, value: int):
        speed = value / 100.0
        self.lbl_speed.setText(f"x{speed:.2f}")
        self.speed_changed.emit(speed)

    def _reset_speed(self):
        self.slider_speed.setValue(100)

    def _on_reverse_clicked(self):
        if self.btn_reverse.isChecked():
            self.btn_boomerang.setChecked(False)
            self.btn_boomerang.setStyleSheet(self._btn_style_normal)
            self.btn_reverse.setStyleSheet(self._mode_active_style)
            self.playback_mode_changed.emit("reverse")
        else:
            self.btn_reverse.setStyleSheet(self._btn_style_normal)
            self.playback_mode_changed.emit("normal")

    def _on_boomerang_clicked(self):
        if self.btn_boomerang.isChecked():
            self.btn_reverse.setChecked(False)
            self.btn_reverse.setStyleSheet(self._btn_style_normal)
            self.btn_boomerang.setStyleSheet(self._mode_active_style)
            self.playback_mode_changed.emit("boomerang")
        else:
            self.btn_boomerang.setStyleSheet(self._btn_style_normal)
            self.playback_mode_changed.emit("normal")

    def set_audio_on(self, on: bool):
        """音声ON/OFF状態をプログラムから設定"""
        if self._audio_on != on:
            self._audio_on = on
            self._update_audio_button()
            self.audio_toggled.emit(self._audio_on)

    def set_audiostretch_on(self, on: bool):
        """AUDIOSTRETCH ON/OFF状態をプログラムから設定"""
        if self._audiostretch_on != on:
            self._audiostretch_on = on
            self._update_audiostretch_button()
            self.audiostretch_toggled.emit(self._audiostretch_on)

    def set_audio_available(self, available: bool):
        """GIF等音声なしの場合にボタンを無効化"""
        self.btn_audio.setEnabled(available)
        self.btn_audiostretch.setEnabled(available)
        if not available:
            self._audio_on = False
            self._update_audio_button()
            self._audiostretch_on = False
            self._update_audiostretch_button()

    @staticmethod
    def _format_time(seconds: float) -> str:
        if seconds < 0:
            seconds = 0
        minutes = int(seconds) // 60
        secs = seconds - minutes * 60
        return f"{minutes:02d}:{secs:06.3f}"
