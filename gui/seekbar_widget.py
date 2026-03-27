"""A/Bマーカー付きカスタムシークバー (PySide6)"""

import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QWidget


class SeekBarWidget(QWidget):
    """2つのA/Bマーカー + 再生ヘッドを持つシークバー"""

    seeked = Signal(float)
    a_changed = Signal(float)
    b_changed = Signal(float)

    # AUDIOSTRETCH スクラブシグナル
    scrub_started = Signal()
    scrub_moved = Signal(float, float)   # (time_sec, velocity)
    scrub_ended = Signal()

    BAR_HEIGHT = 4
    MARKER_RADIUS = 8
    HEAD_WIDTH = 2
    PADDING_X = 16
    HEIGHT = 40

    COLOR_BG = QColor("#2a2a2a")
    COLOR_TRACK = QColor("#555555")
    COLOR_RANGE = QColor("#2196F3")
    COLOR_MARKER = QColor("#64B5F6")
    COLOR_HEAD = QColor("#ffffff")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)

        self._duration = 1.0
        self._a_ratio = 0.0
        self._b_ratio = 1.0
        self._head_ratio = 0.0
        self._dragging: str | None = None

        # AUDIOSTRETCH 速度トラッキング
        self._last_scrub_time_sec: float = 0.0
        self._last_scrub_timestamp: float = 0.0
        self._scrub_velocity: float = 0.0
        self._audiostretch_active: bool = False

    def set_duration(self, duration: float):
        self._duration = max(duration, 0.001)
        self._a_ratio = 0.0
        self._b_ratio = 1.0
        self._head_ratio = 0.0
        self.update()

    def set_head_position(self, time_sec: float):
        self._head_ratio = max(0.0, min(time_sec / self._duration, 1.0))
        self.update()

    def set_a_position(self, time_sec: float):
        self._a_ratio = max(0.0, min(time_sec / self._duration, 1.0))
        self.update()

    def set_b_position(self, time_sec: float):
        self._b_ratio = max(0.0, min(time_sec / self._duration, 1.0))
        self.update()

    def get_a_time(self) -> float:
        return self._a_ratio * self._duration

    def get_b_time(self) -> float:
        return self._b_ratio * self._duration

    def _x_to_ratio(self, x: int) -> float:
        w = self.width()
        track_start = self.PADDING_X
        track_end = w - self.PADDING_X
        track_width = track_end - track_start
        if track_width <= 0:
            return 0.0
        return max(0.0, min((x - track_start) / track_width, 1.0))

    def _ratio_to_x(self, ratio: float) -> float:
        w = self.width()
        track_start = self.PADDING_X
        track_end = w - self.PADDING_X
        return track_start + ratio * (track_end - track_start)

    def paintEvent(self, event):
        w = self.width()
        h = self.height()
        if w <= 0:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        y_center = h // 2
        track_start = self.PADDING_X
        track_end = w - self.PADDING_X

        # 背景
        p.fillRect(self.rect(), self.COLOR_BG)

        # ベーストラック
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.COLOR_TRACK)
        p.drawRect(track_start, y_center - self.BAR_HEIGHT // 2,
                   track_end - track_start, self.BAR_HEIGHT)

        # A-B区間ハイライト
        a_x = self._ratio_to_x(self._a_ratio)
        b_x = self._ratio_to_x(self._b_ratio)
        p.setBrush(self.COLOR_RANGE)
        p.drawRect(int(a_x), y_center - self.BAR_HEIGHT // 2,
                   int(b_x - a_x), self.BAR_HEIGHT)

        # 再生ヘッド
        head_x = int(self._ratio_to_x(self._head_ratio))

        # AUDIOSTRETCH: ドラッグ中のグロー表示
        if self._audiostretch_active and self._dragging == "head":
            glow_color = QColor(33, 150, 243, 80)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow_color)
            p.drawRect(head_x - 6, y_center - 14, 12, 28)

        pen = QPen(self.COLOR_HEAD, self.HEAD_WIDTH)
        p.setPen(pen)
        p.drawLine(head_x, y_center - 12, head_x, y_center + 12)

        # Aマーカー
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.COLOR_MARKER)
        r = self.MARKER_RADIUS
        p.drawEllipse(int(a_x - r), y_center - r, r * 2, r * 2)

        # Bマーカー
        p.drawEllipse(int(b_x - r), y_center - r, r * 2, r * 2)

        p.end()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        x = event.position().x()
        a_x = self._ratio_to_x(self._a_ratio)
        b_x = self._ratio_to_x(self._b_ratio)

        dist_a = abs(x - a_x)
        dist_b = abs(x - b_x)
        grab_threshold = self.MARKER_RADIUS + 4

        if dist_a < grab_threshold and dist_a <= dist_b:
            self._dragging = "a"
        elif dist_b < grab_threshold:
            self._dragging = "b"
        else:
            self._dragging = "head"
            ratio = self._x_to_ratio(int(x))
            self._head_ratio = ratio
            self.update()
            self.seeked.emit(ratio * self._duration)
            # AUDIOSTRETCH: スクラブ開始
            self._last_scrub_time_sec = ratio * self._duration
            self._last_scrub_timestamp = time.perf_counter()
            self._scrub_velocity = 0.0
            self.scrub_started.emit()

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return

        ratio = self._x_to_ratio(int(event.position().x()))

        if self._dragging == "a":
            self._a_ratio = min(ratio, self._b_ratio - 0.001)
            self._a_ratio = max(0.0, self._a_ratio)
            self.update()
            self.a_changed.emit(self._a_ratio * self._duration)
        elif self._dragging == "b":
            self._b_ratio = max(ratio, self._a_ratio + 0.001)
            self._b_ratio = min(1.0, self._b_ratio)
            self.update()
            self.b_changed.emit(self._b_ratio * self._duration)
        elif self._dragging == "head":
            self._head_ratio = ratio
            self.update()
            current_time_sec = ratio * self._duration
            self.seeked.emit(current_time_sec)
            # AUDIOSTRETCH: 速度計算
            now = time.perf_counter()
            dt_wall = now - self._last_scrub_timestamp
            if dt_wall > 0.001:
                dt_video = current_time_sec - self._last_scrub_time_sec
                raw_velocity = dt_video / dt_wall
                # 指数平滑化でジッター除去
                alpha = 0.3
                self._scrub_velocity = (
                    alpha * raw_velocity + (1 - alpha) * self._scrub_velocity
                )
            self._last_scrub_time_sec = current_time_sec
            self._last_scrub_timestamp = now
            self.scrub_moved.emit(current_time_sec, self._scrub_velocity)

    def mouseReleaseEvent(self, event):
        if self._dragging == "head":
            self.scrub_ended.emit()
        self._dragging = None

    def set_audiostretch_active(self, active: bool):
        """AUDIOSTRETCH有効時の視覚フィードバック用フラグ"""
        self._audiostretch_active = active
        self.update()
