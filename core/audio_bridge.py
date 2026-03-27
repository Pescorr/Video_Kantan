"""QMediaPlayer ベースの音声再生ブリッジ

映像は従来の FFmpeg パイプで描画し、音声だけ QMediaPlayer で再生する。
Audio ON/OFF 切替に対応。
"""

from PySide6.QtCore import QUrl, QTimer
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput


class AudioBridge:
    """音声再生専用ラッパー（映像出力なし）"""

    def __init__(self):
        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)
        self._audio_output.setVolume(1.0)

        self._filepath: str | None = None
        self._a_ms: int = 0
        self._b_ms: int = 0
        self._looping: bool = False
        self._loop_guard: bool = False

        self._player.positionChanged.connect(self._check_loop)

    def load(self, filepath: str):
        """音声ソースをロード"""
        self._filepath = filepath
        self._player.setSource(QUrl.fromLocalFile(filepath))

    def load_if_needed(self, filepath: str):
        """同じファイルなら再ロードしない"""
        if filepath != self._filepath:
            self.load(filepath)

    def play(self, start_sec: float):
        """指定位置から再生開始"""
        self._player.setPosition(int(start_sec * 1000))
        self._player.play()

    def pause(self):
        """一時停止"""
        self._player.pause()

    def resume(self):
        """再生再開"""
        self._player.play()

    def stop(self):
        """停止"""
        self._player.stop()

    def seek(self, time_sec: float):
        """指定位置にシーク"""
        self._player.setPosition(int(time_sec * 1000))

    def set_ab(self, a: float, b: float):
        """A-Bループ区間を設定"""
        self._a_ms = int(a * 1000)
        self._b_ms = int(b * 1000)
        self._looping = True

    def _check_loop(self, position_ms: int):
        """positionChanged シグナルで B 地点超過を検出 → A に戻る"""
        if self._loop_guard:
            return
        if self._looping and self._b_ms > 0 and position_ms >= self._b_ms:
            self._loop_guard = True
            self._player.setPosition(self._a_ms)
            QTimer.singleShot(200, self._reset_loop_guard)

    def _reset_loop_guard(self):
        """ループガードをリセット"""
        self._loop_guard = False

    def set_volume(self, vol: float):
        """音量設定 (0.0 - 1.0)"""
        self._audio_output.setVolume(vol)

    def set_playback_rate(self, rate: float):
        """再生速度を設定 (QMediaPlayerネイティブ対応)"""
        self._player.setPlaybackRate(rate)
