"""Video Kantan - 軽量動画エディタ兼プレイヤー"""

import sys
import os


def main():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from core.i18n import init_language
    from gui.app import VideoKantanApp

    app = QApplication(sys.argv)
    init_language()
    window = VideoKantanApp()
    window.show()

    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        QTimer.singleShot(200, lambda: window._load_file(filepath, silent=True))

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
