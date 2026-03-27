"""FFmpeg pipeベースの軽量再生エンジン"""

import threading
import time
from enum import Enum
from typing import Callable, Optional

from PIL import Image

from core.ffmpeg_wrapper import FFmpegWrapper
from core.metadata import VideoMetadata, extract_frame
from core.audio_bridge import AudioBridge


class PlaybackMode(Enum):
    NORMAL = "normal"
    REVERSE = "reverse"
    BOOMERANG = "boomerang"


class PlayerEngine:
    """A-B区間ループ再生エンジン

    FFmpegのpipe出力でフレームをリアルタイムにデコードし、
    コールバックでGUIに渡す。順再生・逆再生・ピンポン再生に対応。
    """

    def __init__(self, ffmpeg: FFmpegWrapper):
        self._ffmpeg = ffmpeg
        self._metadata: Optional[VideoMetadata] = None
        self._filepath: Optional[str] = None

        # 再生状態
        self._playing = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._process = None
        self._stop_event = threading.Event()

        # A-B区間
        self._a_point: float = 0.0
        self._b_point: float = 0.0

        # 音声
        self._audio: Optional[AudioBridge] = None
        self._audio_enabled: bool = False
        self._audio_scrubber = None  # AudioScrubber（逆再生音声用）

        # 現在位置
        self._current_time: float = 0.0

        # 再生速度
        self._speed: float = 1.0

        # 再生モード
        self._playback_mode: PlaybackMode = PlaybackMode.NORMAL

        # AUDIOSTRETCHモード（ONの場合AudioScrubberで全音声を再生）
        self._audiostretch_mode: bool = False

        # コールバック
        self._on_frame: Optional[Callable[[Image.Image, float], None]] = None
        self._on_loop: Optional[Callable[[], None]] = None

    @property
    def is_playing(self) -> bool:
        return self._playing and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._playing and self._paused

    @property
    def current_time(self) -> float:
        return self._current_time

    @property
    def a_point(self) -> float:
        return self._a_point

    @property
    def b_point(self) -> float:
        return self._b_point

    @property
    def speed(self) -> float:
        return self._speed

    def set_speed(self, speed: float):
        """再生速度を変更 (0.10 ~ 3.00)"""
        self._speed = max(0.10, min(speed, 3.00))
        if self._audiostretch_mode:
            # AUDIOSTRETCHモード: AudioScrubberの速度を更新
            if self._audio_scrubber:
                self._audio_scrubber.update_continuous_speed(
                    -self._speed if self._playback_mode == PlaybackMode.REVERSE else self._speed
                )
        else:
            if self._audio and self._audio_enabled:
                self._audio.set_playback_rate(self._speed)
            if self._audio_scrubber:
                self._audio_scrubber.update_continuous_speed(
                    -self._speed if self._playback_mode == PlaybackMode.REVERSE else self._speed
                )

    def set_playback_mode(self, mode: PlaybackMode):
        """再生モードを設定"""
        self._playback_mode = mode

    def set_audio_scrubber(self, scrubber):
        """AudioScrubber を設定（逆再生音声用）"""
        self._audio_scrubber = scrubber

    def set_audiostretch_mode(self, enabled: bool):
        """AUDIOSTRETCHモードの切替

        ONの場合、AudioScrubber（sounddevice）で全音声を再生し
        映像フレームと直接同期する。QMediaPlayerは使用しない。
        """
        self._audiostretch_mode = enabled

    def load(self, filepath: str, metadata: VideoMetadata):
        """動画を登録"""
        self.stop()
        self._filepath = filepath
        self._metadata = metadata
        self._a_point = 0.0
        self._b_point = metadata.duration
        self._current_time = 0.0

    def set_audio(self, bridge: AudioBridge):
        """AudioBridge を設定"""
        self._audio = bridge

    def set_audio_enabled(self, enabled: bool):
        """音声の有効/無効を切り替え"""
        self._audio_enabled = enabled
        if not enabled and self._audio:
            self._audio.stop()
        if not enabled and self._audio_scrubber:
            self._audio_scrubber.stop_continuous()

    def set_ab(self, a: float, b: float):
        """A-B区間を変更"""
        if self._metadata:
            self._a_point = max(0.0, min(a, self._metadata.duration))
            self._b_point = max(self._a_point, min(b, self._metadata.duration))
            if self._audio and self._audio_enabled:
                self._audio.set_ab(self._a_point, self._b_point)

    def play(
        self,
        on_frame: Callable[[Image.Image, float], None],
        on_loop: Optional[Callable[[], None]] = None,
    ):
        """A-B区間の再生を開始

        Args:
            on_frame: フレーム到着時のコールバック(image, timestamp)
            on_loop: ループ時のコールバック
        """
        self.stop()
        if not self._filepath or not self._metadata:
            return

        self._on_frame = on_frame
        self._on_loop = on_loop
        self._playing = True
        self._paused = False
        self._stop_event.clear()

        mode = self._playback_mode

        # 音声開始（モードに応じた処理）
        if self._audio_enabled:
            start_time = self._current_time if self._current_time > self._a_point else self._a_point
            if self._audiostretch_mode:
                # AUDIOSTRETCHモード: AudioScrubberで全音声を再生
                if self._audio_scrubber and self._audio_scrubber.is_loaded:
                    if mode == PlaybackMode.REVERSE:
                        self._audio_scrubber.start_continuous(self._b_point, -self._speed)
                    else:
                        self._audio_scrubber.start_continuous(start_time, self._speed)
            else:
                # 通常モード: AudioBridge (QMediaPlayer) で再生
                if mode in (PlaybackMode.NORMAL, PlaybackMode.BOOMERANG):
                    if self._audio:
                        self._audio.load_if_needed(self._filepath)
                        self._audio.set_ab(self._a_point, self._b_point)
                        self._audio.play(start_time)
                        self._audio.set_playback_rate(self._speed)
                elif mode == PlaybackMode.REVERSE:
                    if self._audio_scrubber and self._audio_scrubber.is_loaded:
                        self._audio_scrubber.start_continuous(self._b_point, -self._speed)

        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def _run_single_pass(self, meta, display_w, display_h, reverse=False):
        """1パス分のフレームを再生（順方向 or 逆方向）

        Args:
            reverse: True = 逆再生（FFmpeg -vf reverse使用）

        Returns:
            True: パス完了（ループ継続）
            False: 停止要求あり
        """
        # A-B全区間をデコード（逆再生時は常にA-B全体が必要）
        if reverse:
            start_time = self._a_point
            ab_duration = self._b_point - self._a_point
        else:
            start_time = self._current_time if self._current_time > self._a_point else self._a_point
            ab_duration = self._b_point - start_time

        if ab_duration <= 0:
            start_time = self._a_point
            ab_duration = self._b_point - self._a_point

        args = [
            "-ss", f"{start_time:.3f}",
            "-t", f"{ab_duration:.3f}",
            "-i", self._filepath,
        ]

        if reverse:
            args.extend(["-vf", "reverse"])

        args.extend([
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{display_w}x{display_h}",
            "pipe:1",
        ])

        try:
            process = self._ffmpeg.run_pipe(args)
            self._process = process
        except Exception:
            return False

        frame_size = display_w * display_h * 3
        original_frame_interval = 1.0 / meta.fps
        frame_index = 0

        while not self._stop_event.is_set():
            # 一時停止中は待機
            while self._paused and not self._stop_event.is_set():
                time.sleep(0.05)

            if self._stop_event.is_set():
                break

            frame_start = time.perf_counter()

            # 1フレーム読み取り
            data = process.stdout.read(frame_size)
            if not data or len(data) < frame_size:
                break  # 区間終了

            try:
                img = Image.frombytes("RGB", (display_w, display_h), data)

                if reverse:
                    # 逆再生: タイムスタンプはB→Aに進行
                    timestamp = self._b_point - frame_index * original_frame_interval
                    timestamp = max(timestamp, self._a_point)
                else:
                    timestamp = start_time + frame_index * original_frame_interval

                self._current_time = timestamp

                if self._on_frame and not self._stop_event.is_set():
                    self._on_frame(img, timestamp)

                # AUDIOSTRETCHモード: 映像フレームに音声位置を同期
                if self._audiostretch_mode and self._audio_scrubber and self._audio_enabled:
                    self._audio_scrubber.sync_to_timestamp(timestamp)
            except Exception:
                break

            frame_index += 1

            # FPSに合わせてスリープ（速度反映）
            display_interval = original_frame_interval / self._speed
            elapsed = time.perf_counter() - frame_start
            sleep_time = display_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        # プロセスクリーンアップ
        try:
            process.kill()
            process.wait(timeout=2)
        except Exception:
            pass
        self._process = None

        return not self._stop_event.is_set()

    def _start_pass_audio(self, reverse: bool):
        """パス切替時の音声制御"""
        if not self._audio_enabled:
            return

        if self._audiostretch_mode:
            # AUDIOSTRETCHモード: AudioScrubberのみ使用
            if self._audio_scrubber and self._audio_scrubber.is_loaded:
                self._audio_scrubber.stop_continuous()
                if reverse:
                    self._audio_scrubber.start_continuous(self._b_point, -self._speed)
                else:
                    self._audio_scrubber.start_continuous(self._a_point, self._speed)
            return

        if reverse:
            # AudioBridge停止 → AudioScrubberで逆再生音声
            if self._audio:
                self._audio.pause()
            if self._audio_scrubber and self._audio_scrubber.is_loaded:
                self._audio_scrubber.start_continuous(self._b_point, -self._speed)
        else:
            # AudioScrubber停止 → AudioBridgeで順再生
            if self._audio_scrubber:
                self._audio_scrubber.stop_continuous()
            if self._audio:
                self._audio.seek(self._a_point)
                self._audio.set_playback_rate(self._speed)
                self._audio.resume()

    def _playback_loop(self):
        """再生ループ（バックグラウンドスレッド）"""
        meta = self._metadata
        if not meta:
            return

        # 表示用のサイズを計算（大きすぎる場合はリサイズ）
        display_w, display_h = self._calc_display_size(meta.width, meta.height)
        mode = self._playback_mode

        while not self._stop_event.is_set():
            if mode == PlaybackMode.NORMAL:
                completed = self._run_single_pass(meta, display_w, display_h, reverse=False)

            elif mode == PlaybackMode.REVERSE:
                self._current_time = self._a_point
                completed = self._run_single_pass(meta, display_w, display_h, reverse=True)

            elif mode == PlaybackMode.BOOMERANG:
                # 順再生パス
                self._start_pass_audio(reverse=False)
                completed = self._run_single_pass(meta, display_w, display_h, reverse=False)
                if not completed:
                    break
                # 逆再生パス
                self._start_pass_audio(reverse=True)
                self._current_time = self._a_point
                completed = self._run_single_pass(meta, display_w, display_h, reverse=True)
            else:
                completed = False

            if not completed:
                break

            # ループ: A地点に戻る
            self._current_time = self._a_point
            if self._audio_enabled and self._audiostretch_mode:
                # AUDIOSTRETCHモード: AudioScrubberリセット
                if self._audio_scrubber and self._audio_scrubber.is_loaded:
                    self._audio_scrubber.stop_continuous()
                    if mode == PlaybackMode.NORMAL:
                        self._audio_scrubber.start_continuous(self._a_point, self._speed)
                    elif mode == PlaybackMode.REVERSE:
                        self._audio_scrubber.start_continuous(self._b_point, -self._speed)
                    # BOOMERANGは_start_pass_audioで処理されるため不要
            elif self._audio_enabled:
                if mode == PlaybackMode.NORMAL and self._audio:
                    self._audio.seek(self._a_point)
                elif mode == PlaybackMode.REVERSE and self._audio_scrubber:
                    self._audio_scrubber.stop_continuous()
                    self._audio_scrubber.start_continuous(self._b_point, -self._speed)
            if self._on_loop:
                self._on_loop()

        self._playing = False

    def pause(self):
        """一時停止"""
        if self._playing:
            self._paused = True
            if self._audiostretch_mode:
                if self._audio_scrubber:
                    self._audio_scrubber.stop_continuous()
            else:
                if self._audio and self._audio_enabled:
                    self._audio.pause()
                if self._audio_scrubber:
                    self._audio_scrubber.stop_continuous()

    def resume(self):
        """一時停止解除"""
        if self._playing:
            self._paused = False
            mode = self._playback_mode
            if self._audiostretch_mode:
                if self._audio_scrubber and self._audio_scrubber.is_loaded and self._audio_enabled:
                    if mode == PlaybackMode.REVERSE:
                        self._audio_scrubber.start_continuous(self._current_time, -self._speed)
                    else:
                        self._audio_scrubber.start_continuous(self._current_time, self._speed)
            else:
                if mode == PlaybackMode.NORMAL or mode == PlaybackMode.BOOMERANG:
                    if self._audio and self._audio_enabled:
                        self._audio.resume()
                elif mode == PlaybackMode.REVERSE:
                    if self._audio_scrubber and self._audio_scrubber.is_loaded and self._audio_enabled:
                        self._audio_scrubber.start_continuous(self._current_time, -self._speed)

    def toggle_pause(self):
        """再生/一時停止切り替え"""
        if self._paused:
            self.resume()
        elif self._playing:
            self.pause()

    def stop(self):
        """再生停止"""
        self._stop_event.set()
        self._playing = False
        self._paused = False
        if self._audio and self._audio_enabled:
            self._audio.stop()
        if self._audio_scrubber:
            self._audio_scrubber.stop_continuous()

        if self._process and self._process.poll() is None:
            try:
                self._process.kill()
            except Exception:
                pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

        self._process = None
        self._thread = None

    def seek(self, timestamp: float) -> Optional[Image.Image]:
        """指定時刻のフレームを取得（一時停止状態用）"""
        if not self._filepath or not self._metadata:
            return None

        self._current_time = timestamp
        if self._audio and self._audio_enabled:
            self._audio.seek(timestamp)
        return extract_frame(
            self._ffmpeg,
            self._filepath,
            timestamp,
            self._metadata.width,
            self._metadata.height,
        )

    def seek_to_a(self) -> Optional[Image.Image]:
        """A地点にシーク"""
        return self.seek(self._a_point)

    def seek_to_b(self) -> Optional[Image.Image]:
        """B地点にシーク"""
        return self.seek(self._b_point)

    @staticmethod
    def _calc_display_size(width: int, height: int, max_w: int = 760, max_h: int = 400) -> tuple[int, int]:
        """アスペクト比を維持してリサイズ後のサイズを計算"""
        if width <= max_w and height <= max_h:
            # 2の倍数に丸める
            return width - (width % 2), height - (height % 2)

        ratio = min(max_w / width, max_h / height)
        new_w = int(width * ratio)
        new_h = int(height * ratio)
        # 2の倍数に丸める（FFmpegの要件）
        return new_w - (new_w % 2), new_h - (new_h % 2)
