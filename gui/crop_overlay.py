"""クロップ用の矩形選択オーバーレイ (PySide6)"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import QWidget


class CropOverlay(QWidget):
    """動画表示の上に重ねる透明オーバーレイ"""

    crop_changed = Signal(int, int, int, int)

    HANDLE_SIZE = 8
    COLOR_RECT = QColor("#2196F3")
    COLOR_MASK = QColor(0, 0, 0, 128)
    COLOR_HANDLE = QColor("#ffffff")

    def __init__(self, parent: QWidget, video_width: int, video_height: int):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self._video_width = video_width
        self._video_height = video_height

        self._rect_x1 = 0.0
        self._rect_y1 = 0.0
        self._rect_x2 = 0.0
        self._rect_y2 = 0.0

        self._dragging: str | None = None
        self._drag_start_x = 0.0
        self._drag_start_y = 0.0
        self._drag_start_rect = (0.0, 0.0, 0.0, 0.0)

        self._display_x = 0
        self._display_y = 0
        self._display_w = 0
        self._display_h = 0
        self._active = False

    def activate(self, display_x: int, display_y: int, display_w: int, display_h: int):
        self._display_x = display_x
        self._display_y = display_y
        self._display_w = display_w
        self._display_h = display_h

        margin_x = display_w * 0.1
        margin_y = display_h * 0.1
        self._rect_x1 = display_x + margin_x
        self._rect_y1 = display_y + margin_y
        self._rect_x2 = display_x + display_w - margin_x
        self._rect_y2 = display_y + display_h - margin_y

        self._active = True
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.update()

    def deactivate(self):
        self._active = False
        self.hide()

    def get_crop_rect(self) -> tuple[int, int, int, int] | None:
        if not self._active or self._display_w <= 0:
            return None

        scale_x = self._video_width / self._display_w
        scale_y = self._video_height / self._display_h

        x = int((self._rect_x1 - self._display_x) * scale_x)
        y = int((self._rect_y1 - self._display_y) * scale_y)
        w = int((self._rect_x2 - self._rect_x1) * scale_x)
        h = int((self._rect_y2 - self._rect_y1) * scale_y)

        x = max(0, min(x, self._video_width))
        y = max(0, min(y, self._video_height))
        w = max(2, min(w, self._video_width - x))
        h = max(2, min(h, self._video_height - y))
        w = w - (w % 2)
        h = h - (h % 2)

        return (x, y, w, h)

    def paintEvent(self, event):
        if not self._active:
            return

        p = QPainter(self)
        x1, y1 = int(self._rect_x1), int(self._rect_y1)
        x2, y2 = int(self._rect_x2), int(self._rect_y2)
        dx, dy = self._display_x, self._display_y
        dw, dh = self._display_w, self._display_h

        # 半透明マスク
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.COLOR_MASK)
        p.drawRect(dx, dy, dw, y1 - dy)
        p.drawRect(dx, y2, dw, dy + dh - y2)
        p.drawRect(dx, y1, x1 - dx, y2 - y1)
        p.drawRect(x2, y1, dx + dw - x2, y2 - y1)

        # 選択矩形
        pen = QPen(self.COLOR_RECT, 2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(x1, y1, x2 - x1, y2 - y1)

        # コーナーハンドル
        hs = self.HANDLE_SIZE
        p.setPen(QPen(self.COLOR_RECT, 1))
        p.setBrush(self.COLOR_HANDLE)
        for hx, hy in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
            p.drawRect(hx - hs // 2, hy - hs // 2, hs, hs)

        # クロップサイズ表示
        crop = self.get_crop_rect()
        if crop:
            _, _, cw, ch = crop
            p.setPen(self.COLOR_RECT)
            p.setFont(QFont("Consolas", 10))
            p.drawText((x1 + x2) // 2 - 30, y1 - 4, f"{cw}x{ch}")

        p.end()

    def mousePressEvent(self, event):
        if not self._active or event.button() != Qt.MouseButton.LeftButton:
            return

        x, y = event.position().x(), event.position().y()
        self._drag_start_x = x
        self._drag_start_y = y
        self._drag_start_rect = (self._rect_x1, self._rect_y1, self._rect_x2, self._rect_y2)

        hs = self.HANDLE_SIZE
        if abs(x - self._rect_x1) < hs and abs(y - self._rect_y1) < hs:
            self._dragging = "tl"
        elif abs(x - self._rect_x2) < hs and abs(y - self._rect_y1) < hs:
            self._dragging = "tr"
        elif abs(x - self._rect_x1) < hs and abs(y - self._rect_y2) < hs:
            self._dragging = "bl"
        elif abs(x - self._rect_x2) < hs and abs(y - self._rect_y2) < hs:
            self._dragging = "br"
        elif self._rect_x1 < x < self._rect_x2 and self._rect_y1 < y < self._rect_y2:
            self._dragging = "move"
        else:
            self._dragging = "new"
            self._rect_x1 = x
            self._rect_y1 = y
            self._rect_x2 = x
            self._rect_y2 = y

    def mouseMoveEvent(self, event):
        if not self._active or not self._dragging:
            return

        x, y = event.position().x(), event.position().y()
        ddx = x - self._drag_start_x
        ddy = y - self._drag_start_y
        sx1, sy1, sx2, sy2 = self._drag_start_rect

        if self._dragging == "move":
            self._rect_x1 = sx1 + ddx
            self._rect_y1 = sy1 + ddy
            self._rect_x2 = sx2 + ddx
            self._rect_y2 = sy2 + ddy
        elif self._dragging == "tl":
            self._rect_x1 = sx1 + ddx
            self._rect_y1 = sy1 + ddy
        elif self._dragging == "tr":
            self._rect_x2 = sx2 + ddx
            self._rect_y1 = sy1 + ddy
        elif self._dragging == "bl":
            self._rect_x1 = sx1 + ddx
            self._rect_y2 = sy2 + ddy
        elif self._dragging == "br":
            self._rect_x2 = sx2 + ddx
            self._rect_y2 = sy2 + ddy
        elif self._dragging == "new":
            self._rect_x2 = x
            self._rect_y2 = y

        self._normalize_rect()
        self._clamp_rect()
        self.update()

    def mouseReleaseEvent(self, event):
        if self._dragging:
            self._dragging = None
            crop = self.get_crop_rect()
            if crop:
                self.crop_changed.emit(*crop)

    def _normalize_rect(self):
        if self._rect_x1 > self._rect_x2:
            self._rect_x1, self._rect_x2 = self._rect_x2, self._rect_x1
        if self._rect_y1 > self._rect_y2:
            self._rect_y1, self._rect_y2 = self._rect_y2, self._rect_y1

    def _clamp_rect(self):
        dx, dy = self._display_x, self._display_y
        dw, dh = self._display_w, self._display_h
        self._rect_x1 = max(dx, min(self._rect_x1, dx + dw))
        self._rect_y1 = max(dy, min(self._rect_y1, dy + dh))
        self._rect_x2 = max(dx, min(self._rect_x2, dx + dw))
        self._rect_y2 = max(dy, min(self._rect_y2, dy + dh))
