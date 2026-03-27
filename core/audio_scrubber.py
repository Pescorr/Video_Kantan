"""テープスクラブ方式のリアルタイム音声出力エンジン

シークバーのドラッグ速度・方向に応じて音声をリアルタイム再生する。
- ゆっくり前方 → スロー再生（ピッチ低下）
- 速く前方 → 高速再生（ピッチ上昇）
- 後方 → 逆再生
- 停止 → 無音
"""

import subprocess
import sys
import threading
from typing import Optional

import numpy as np

try:
    import sounddevice as sd
except ImportError:
    sd = None


SAMPLE_RATE = 44100
CHANNELS = 2
BLOCK_SIZE = 512  # ~11.6ms @ 44100Hz


class AudioScrubber:
    """AUDIOSTRETCH: テープスクラブ音声エンジン"""

    def __init__(self):
        self._audio_data: Optional[np.ndarray] = None  # (n_samples, 2) float32
        self._duration: float = 0.0
        self._loaded: bool = False

        # スクラブ状態（オーディオコールバックスレッドとGUIスレッド間で共有）
        self._lock = threading.Lock()
        self._current_pos: float = 0.0    # サンプル位置（浮動小数点）
        self._scrub_speed: float = 0.0    # サンプル/出力サンプル比率
        self._active: bool = False
        self._volume: float = 1.0

        self._stream: Optional[object] = None  # sd.OutputStream

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def load(self, filepath: str, ffmpeg_path: str) -> bool:
        """FFmpegで音声全体をPCM float32として抽出

        Args:
            filepath: 動画ファイルパス
            ffmpeg_path: ffmpegバイナリパス

        Returns:
            True: 抽出成功, False: 失敗（音声なし等）
        """
        if sd is None:
            return False

        args = [
            ffmpeg_path,
            "-i", filepath,
            "-vn",                  # 映像除外
            "-f", "f32le",          # raw float32 little-endian
            "-acodec", "pcm_f32le",
            "-ac", str(CHANNELS),   # ステレオ
            "-ar", str(SAMPLE_RATE),
            "pipe:1",
        ]

        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                startupinfo=startupinfo,
            )
            raw_data = process.stdout.read()
            process.wait()
        except Exception:
            return False

        if not raw_data or len(raw_data) < CHANNELS * 4:
            return False

        # numpy配列に変換: (n_samples, 2)
        samples = np.frombuffer(raw_data, dtype=np.float32)
        # チャンネル数で割り切れない端数は切り捨て
        n_samples = len(samples) // CHANNELS
        self._audio_data = samples[:n_samples * CHANNELS].reshape(n_samples, CHANNELS)
        self._duration = n_samples / SAMPLE_RATE
        self._loaded = True
        return True

    def unload(self):
        """音声データを解放"""
        self.stop_scrub()
        self._audio_data = None
        self._loaded = False
        self._duration = 0.0

    def start_scrub(self):
        """スクラブ出力を開始（sounddevice OutputStream起動）"""
        if sd is None or not self._loaded or self._stream is not None:
            return

        with self._lock:
            self._active = True
            self._scrub_speed = 0.0

        self._stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            callback=self._audio_callback,
        )
        self._stream.start()

    def start_continuous(self, time_sec: float, speed: float):
        """連続再生を開始（逆再生対応: speed < 0 で逆再生）

        Args:
            time_sec: 開始位置（秒）
            speed: 再生速度（正=順再生、負=逆再生）
        """
        if sd is None or not self._loaded:
            return

        self.stop_continuous()

        with self._lock:
            self._current_pos = time_sec * SAMPLE_RATE
            self._scrub_speed = speed
            self._active = True

        self._stream = sd.OutputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop_continuous(self):
        """連続再生を停止"""
        with self._lock:
            self._active = False
            self._scrub_speed = 0.0

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def update_continuous_speed(self, speed: float):
        """再生中に速度を変更"""
        with self._lock:
            self._scrub_speed = speed

    def sync_to_timestamp(self, time_sec: float):
        """映像タイムスタンプに音声位置を同期（ドリフト補正）

        100ms以上ずれている場合のみ位置を修正する。
        """
        with self._lock:
            if not self._active:
                return
            target_pos = time_sec * SAMPLE_RATE
            if abs(self._current_pos - target_pos) > SAMPLE_RATE * 0.1:
                self._current_pos = target_pos

    def stop_scrub(self):
        """スクラブ出力を停止"""
        with self._lock:
            self._active = False
            self._scrub_speed = 0.0

        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def update_scrub(self, time_sec: float, velocity: float):
        """GUI側からスクラブ位置と速度を更新

        Args:
            time_sec: 現在のシーク位置（秒）
            velocity: スクラブ速度（秒/秒）。正=前方、負=後方
        """
        sample_pos = time_sec * SAMPLE_RATE
        with self._lock:
            self._current_pos = sample_pos
            self._scrub_speed = velocity

    def set_volume(self, vol: float):
        """音量設定 (0.0 - 1.0)"""
        with self._lock:
            self._volume = max(0.0, min(vol, 1.0))

    def _audio_callback(self, outdata: np.ndarray, frames: int,
                        time_info, status):
        """sounddeviceコールバック（オーディオスレッドで呼ばれる）

        テープスクラブ: current_posからscrub_speed分のサンプルを読み出す。
        線形補間で滑らかに、速度に応じた自然なピッチ変化。
        """
        with self._lock:
            if not self._active or self._audio_data is None:
                outdata[:] = 0
                return
            speed = self._scrub_speed
            pos = self._current_pos
            volume = self._volume

        # 速度がほぼ0 → 無音
        if abs(speed) < 0.05:
            outdata[:] = 0
            return

        data = self._audio_data
        n_total = len(data)

        # フレームごとにサンプルを生成（線形補間）
        for i in range(frames):
            if 0 <= pos < n_total - 1:
                idx = int(pos)
                frac = pos - idx
                outdata[i] = data[idx] * (1.0 - frac) + data[idx + 1] * frac
            elif 0 <= int(pos) < n_total:
                outdata[i] = data[int(pos)]
            else:
                outdata[i] = 0
            pos += speed

        # 速度に応じた音量スケーリング（極端な速度での音割れ防止）
        speed_abs = abs(speed)
        if speed_abs > 1.0:
            vol_scale = 1.0 / speed_abs
        else:
            vol_scale = 1.0
        outdata *= volume * vol_scale

        with self._lock:
            self._current_pos = pos
