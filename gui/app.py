"""Video Kantan メインアプリケーション (PySide6)"""

import os
import threading

from PySide6.QtCore import Qt, QObject, Signal, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QLabel, QFileDialog, QMessageBox,
    QProgressDialog,
)

from PIL import Image

from core.ffmpeg_wrapper import FFmpegWrapper, FFmpegError, CancelledError
from core.ffmpeg_downloader import download_ffmpeg, is_ffmpeg_available
from core.metadata import VideoMetadata, get_metadata
from core.player_engine import PlayerEngine, PlaybackMode
from core.operations import ExportOptions, build_export_args, generate_output_path
from core.license import check_license_cached
from core.audio_bridge import AudioBridge
from core.audio_scrubber import AudioScrubber
from core.i18n import tr, get_language, set_language
from core.version import __version__, APP_NAME
from gui.player_widget import PlayerWidget
from gui.options_panel import OptionsPanel
from gui.crop_overlay import CropOverlay


class _ThreadBridge(QObject):
    """バックグラウンドスレッドからUIへのシグナルブリッジ"""
    frame_received = Signal(object, float)
    progress_updated = Signal(float)
    export_done = Signal()
    export_cancelled = Signal()
    export_error = Signal(str)


# ダークテーマ QSS
_DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1a1a1a;
    color: #ffffff;
}
QPushButton {
    background-color: #333333;
    color: #ffffff;
    border: none;
    padding: 6px 12px;
    font-size: 11pt;
}
QPushButton:hover {
    background-color: #444444;
}
QPushButton:disabled {
    background-color: #2a2a2a;
    color: #666666;
}
QLineEdit {
    background-color: #2a2a2a;
    color: #ffffff;
    border: none;
    padding: 4px;
    font-family: Consolas;
    font-size: 10pt;
    selection-background-color: #2196F3;
}
QCheckBox {
    color: #ffffff;
    font-size: 11pt;
    spacing: 6px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    background-color: #333333;
    border: 1px solid #555555;
}
QCheckBox::indicator:checked {
    background-color: #2196F3;
}
QSlider::groove:horizontal {
    background: #333333;
    height: 4px;
}
QSlider::handle:horizontal {
    background: #2196F3;
    width: 16px;
    margin: -6px 0;
}
QProgressBar {
    background-color: #333333;
    border: none;
    text-align: center;
    color: #ffffff;
}
QProgressBar::chunk {
    background-color: #2196F3;
}
#headerBar {
    background-color: #222222;
}
#langButton {
    background: transparent;
    border: none;
    padding: 0px;
    font-size: 13px;
}
#langButton:hover {
    background-color: #333333;
}
"""


class VideoKantanApp(QMainWindow):
    """メインアプリケーション"""

    def __init__(self):
        super().__init__()

        self._licensed = check_license_cached()
        self._base_title = f"{APP_NAME} v{__version__}"
        title = self._base_title if self._licensed else self._base_title + tr("title_free_suffix")
        self.setWindowTitle(title)
        self.resize(850, 700)
        self.setMinimumSize(640, 500)
        self.setStyleSheet(_DARK_STYLE)
        self.setAcceptDrops(True)

        # コアコンポーネント
        try:
            self._ffmpeg = FFmpegWrapper()
        except FileNotFoundError:
            if self._offer_ffmpeg_download():
                self._ffmpeg = FFmpegWrapper()
            else:
                QMessageBox.critical(
                    self,
                    tr("err_ffmpeg_needed_title"),
                    tr("err_ffmpeg_needed_msg"),
                )
                raise

        self._engine = PlayerEngine(self._ffmpeg)
        self._audio_bridge = AudioBridge()
        self._engine.set_audio(self._audio_bridge)
        self._audio_scrubber = AudioScrubber()
        self._engine.set_audio_scrubber(self._audio_scrubber)
        self._audiostretch_enabled = False
        self._metadata: VideoMetadata | None = None
        self._crop_overlay: CropOverlay | None = None
        self._output_path: str | None = None

        # スレッドブリッジ
        self._bridge = _ThreadBridge()
        self._bridge.frame_received.connect(self._on_frame_display)
        self._bridge.progress_updated.connect(self._on_progress)
        self._bridge.export_done.connect(self._export_done)
        self._bridge.export_cancelled.connect(self._export_cancelled)
        self._bridge.export_error.connect(self._export_error)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== ヘッダーバー =====
        header = QWidget()
        header.setObjectName("headerBar")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 6, 8, 6)

        self.btn_browse = QPushButton("📁")
        self.btn_browse.setFixedWidth(40)
        self.btn_browse.clicked.connect(self._browse_file)
        header_layout.addWidget(self.btn_browse)

        self.entry_path = QLineEdit()
        self.entry_path.setPlaceholderText(tr("placeholder_path"))
        self.entry_path.returnPressed.connect(self._open_from_entry)
        header_layout.addWidget(self.entry_path, stretch=1)

        self.btn_open = QPushButton(tr("btn_open"))
        self.btn_open.clicked.connect(self._open_from_entry)
        header_layout.addWidget(self.btn_open)

        self.lbl_info = QLabel("")
        self.lbl_info.setStyleSheet("color: #888888; font-family: Consolas; font-size: 9pt;")
        header_layout.addWidget(self.lbl_info)

        main_layout.addWidget(header)

        # ===== プレイヤー =====
        self._player = PlayerWidget()
        self._player.play_pause.connect(self._toggle_play)
        self._player.seek.connect(self._on_seek)
        self._player.prev_frame.connect(self._prev_frame)
        self._player.next_frame.connect(self._next_frame)
        self._player.goto_a.connect(self._goto_a)
        self._player.goto_b.connect(self._goto_b)
        self._player.seekbar.a_changed.connect(self._on_a_changed)
        self._player.seekbar.b_changed.connect(self._on_b_changed)
        self._player.set_a_to_current.connect(self._set_a_to_current)
        self._player.set_b_to_current.connect(self._set_b_to_current)
        self._player.audio_toggled.connect(self._on_audio_toggled)
        self._player.audiostretch_toggled.connect(self._on_audiostretch_toggled)
        self._player.speed_changed.connect(self._on_speed_changed)
        self._player.playback_mode_changed.connect(self._on_playback_mode_changed)
        self._player.seekbar.scrub_started.connect(self._on_scrub_started)
        self._player.seekbar.scrub_moved.connect(self._on_scrub_moved)
        self._player.seekbar.scrub_ended.connect(self._on_scrub_ended)
        main_layout.addWidget(self._player, stretch=1)

        # ===== オプションパネル =====
        self._options = OptionsPanel()
        self._options.save_gif.connect(lambda: self._save("gif"))
        self._options.save_mp4.connect(lambda: self._save("mp4"))
        self._options.cancel.connect(self._cancel_export)
        self._options.crop_toggled.connect(self._toggle_crop)
        self._options.open_folder.connect(self._open_output_folder)
        self._options.set_enabled(False)
        self._options.set_license_status(self._licensed)
        main_layout.addWidget(self._options)

        # ===== フッター（言語切替ボタン右下） =====
        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 20, 6)
        footer_layout.setSpacing(0)
        footer_layout.addStretch()

        self.btn_lang = QPushButton()
        self.btn_lang.setObjectName("langButton")
        self.btn_lang.setFixedSize(28, 20)
        self.btn_lang.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lang.clicked.connect(self._toggle_language)
        self._update_lang_button()
        footer_layout.addWidget(self.btn_lang)

        main_layout.addWidget(footer)

    # ===== 音声トグル =====

    def _on_audio_toggled(self, enabled: bool):
        self._engine.set_audio_enabled(enabled)

    # ===== AUDIOSTRETCH =====

    def _on_speed_changed(self, speed: float):
        """再生速度変更"""
        self._engine.set_speed(speed)

    def _on_playback_mode_changed(self, mode_str: str):
        """再生モード変更"""
        mode_map = {
            "normal": PlaybackMode.NORMAL,
            "reverse": PlaybackMode.REVERSE,
            "boomerang": PlaybackMode.BOOMERANG,
        }
        mode = mode_map.get(mode_str, PlaybackMode.NORMAL)
        self._engine.set_playback_mode(mode)
        # 再生中の場合、モード変更を即反映するため再起動
        if self._engine.is_playing or self._engine.is_paused:
            saved_time = self._engine.current_time
            self._engine.stop()
            self._engine._current_time = saved_time
            a = self._player.seekbar.get_a_time()
            b = self._player.seekbar.get_b_time()
            self._engine.set_ab(a, b)
            self._engine.play(
                on_frame=self._on_frame_received,
                on_loop=self._on_loop,
            )
            self._player.update_play_state(True)

    def _on_audiostretch_toggled(self, enabled: bool):
        self._audiostretch_enabled = enabled
        self._engine.set_audiostretch_mode(enabled)
        self._player.seekbar.set_audiostretch_active(enabled)
        if not enabled:
            self._audio_scrubber.stop_scrub()

    def _on_scrub_started(self):
        if not self._audiostretch_enabled or not self._audio_scrubber.is_loaded:
            return
        if self._engine.is_playing:
            self._engine.stop()
            self._player.update_play_state(False)
        self._audio_scrubber.start_scrub()

    def _on_scrub_moved(self, time_sec: float, velocity: float):
        if not self._audiostretch_enabled:
            return
        self._audio_scrubber.update_scrub(time_sec, velocity)

    def _on_scrub_ended(self):
        if not self._audiostretch_enabled:
            return
        self._audio_scrubber.stop_scrub()

    # ===== 言語切替 =====

    def _toggle_language(self):
        new_lang = "en" if get_language() == "ja" else "ja"
        set_language(new_lang)
        self._update_lang_button()
        self._retranslate()
        self._options.retranslate()
        self._player.video_display.update()

    def _update_lang_button(self):
        if get_language() == "ja":
            self.btn_lang.setText("JA")
            self.btn_lang.setToolTip("English に切替")
        else:
            self.btn_lang.setText("EN")
            self.btn_lang.setToolTip("日本語に切替")

    def _retranslate(self):
        suffix = "" if self._licensed else tr("title_free_suffix")
        if self._metadata:
            filename = os.path.basename(self._metadata.filepath)
            self.setWindowTitle(f"{self._base_title}{suffix} - {filename}")
        else:
            self.setWindowTitle(f"{self._base_title}{suffix}")
        self.entry_path.setPlaceholderText(tr("placeholder_path"))
        self.btn_open.setText(tr("btn_open"))

    # ===== ドラッグ&ドロップ =====

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            filepath = urls[0].toLocalFile()
            if os.path.isfile(filepath):
                self._load_file(filepath, silent=True)

    # ===== ファイル操作 =====

    def _browse_file(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            tr("dialog_select_file"),
            "",
            tr("filter_video"),
        )
        if not filepath:
            return
        self._load_file(filepath)

    def _open_from_entry(self):
        filepath = self.entry_path.text().strip()
        if not filepath:
            return
        self._load_file(filepath)

    def _load_file(self, filepath: str, silent: bool = False):
        try:
            metadata = get_metadata(self._ffmpeg, filepath)
        except Exception as e:
            if not silent:
                QMessageBox.critical(self, tr("err_load_title"), tr("err_load_msg", error=str(e)))
            return

        self._engine.stop()
        self._metadata = metadata
        meta = self._metadata

        self.entry_path.setText(filepath)
        self.lbl_info.setText(
            f"{meta.width}x{meta.height} | {meta.duration:.2f}s | {meta.fps:.2f}FPS"
        )
        suffix = "" if self._licensed else tr("title_free_suffix")
        self.setWindowTitle(f"{self._base_title}{suffix} - {os.path.basename(filepath)}")

        self._player.set_duration(meta.duration)
        self._player.update_ab_labels(0.0, meta.duration)
        self._engine.load(filepath, meta)

        QTimer.singleShot(100, self._show_first_frame)

        self._options.set_enabled(True)
        self._output_path = None
        self._player.set_audio_available(not meta.is_gif)
        if not meta.is_gif:
            self._player.set_audio_on(True)
            self._player.set_audiostretch_on(True)

        # AUDIOSTRETCH: 音声データをバックグラウンドで事前抽出
        self._audio_scrubber.unload()
        if not meta.is_gif:
            threading.Thread(
                target=self._load_audio_scrub_data,
                args=(filepath,),
                daemon=True,
            ).start()

        if self._crop_overlay:
            self._crop_overlay.deactivate()
            self._crop_overlay.deleteLater()
            self._crop_overlay = None
        self._options.cb_crop.setChecked(False)

    def _load_audio_scrub_data(self, filepath: str):
        """AUDIOSTRETCH用の音声データをバックグラウンドで抽出"""
        self._audio_scrubber.load(filepath, self._ffmpeg.ffmpeg_path)

    def _show_first_frame(self):
        if not self._metadata:
            return
        frame = self._engine.seek(0.0)
        if frame:
            self._player.display_frame(frame, 0.0)

    # ===== 再生コントロール =====

    def _toggle_play(self):
        if not self._metadata:
            return

        if self._engine.is_playing:
            if self._engine.is_paused:
                self._engine.resume()
                self._player.update_play_state(True)
            else:
                self._engine.pause()
                self._player.update_play_state(False)
        else:
            a = self._player.seekbar.get_a_time()
            b = self._player.seekbar.get_b_time()
            self._engine.set_ab(a, b)
            self._engine.play(
                on_frame=self._on_frame_received,
                on_loop=self._on_loop,
            )
            self._player.update_play_state(True)

    def _on_frame_received(self, image: Image.Image, timestamp: float):
        self._bridge.frame_received.emit(image, timestamp)

    def _on_frame_display(self, image: Image.Image, timestamp: float):
        self._player.display_frame(image, timestamp)

    def _on_loop(self):
        pass

    def _on_seek(self, time_sec: float):
        if not self._metadata:
            return
        if self._engine.is_playing:
            self._engine.stop()
            self._player.update_play_state(False)
        frame = self._engine.seek(time_sec)
        if frame:
            self._player.display_frame(frame, time_sec)

    def _prev_frame(self):
        if not self._metadata:
            return
        if self._engine.is_playing:
            self._engine.stop()
            self._player.update_play_state(False)
        dt = 1.0 / self._metadata.fps
        new_time = max(0, self._engine.current_time - dt)
        frame = self._engine.seek(new_time)
        if frame:
            self._player.display_frame(frame, new_time)

    def _next_frame(self):
        if not self._metadata:
            return
        if self._engine.is_playing:
            self._engine.stop()
            self._player.update_play_state(False)
        dt = 1.0 / self._metadata.fps
        new_time = min(self._metadata.duration, self._engine.current_time + dt)
        frame = self._engine.seek(new_time)
        if frame:
            self._player.display_frame(frame, new_time)

    def _goto_a(self):
        if not self._metadata:
            return
        if self._engine.is_playing:
            self._engine.stop()
            self._player.update_play_state(False)
        a_time = self._player.seekbar.get_a_time()
        frame = self._engine.seek(a_time)
        if frame:
            self._player.display_frame(frame, a_time)

    def _goto_b(self):
        if not self._metadata:
            return
        if self._engine.is_playing:
            self._engine.stop()
            self._player.update_play_state(False)
        b_time = self._player.seekbar.get_b_time()
        frame = self._engine.seek(b_time)
        if frame:
            self._player.display_frame(frame, b_time)

    # ===== A/Bマーカー =====

    def _on_a_changed(self, time_sec: float):
        b_time = self._player.seekbar.get_b_time()
        self._player.update_ab_labels(time_sec, b_time)
        self._engine.set_ab(time_sec, b_time)

    def _on_b_changed(self, time_sec: float):
        a_time = self._player.seekbar.get_a_time()
        self._player.update_ab_labels(a_time, time_sec)
        self._engine.set_ab(a_time, time_sec)

    def _set_a_to_current(self):
        if not self._metadata:
            return
        current = self._engine.current_time
        b_time = self._player.seekbar.get_b_time()
        if current >= b_time:
            return
        self._player.seekbar.set_a_position(current)
        self._player.update_ab_labels(current, b_time)
        self._engine.set_ab(current, b_time)

    def _set_b_to_current(self):
        if not self._metadata:
            return
        current = self._engine.current_time
        a_time = self._player.seekbar.get_a_time()
        if current <= a_time:
            return
        self._player.seekbar.set_b_position(current)
        self._player.update_ab_labels(a_time, current)
        self._engine.set_ab(a_time, current)

    # ===== クロップ =====

    def _toggle_crop(self, enabled: bool):
        if not self._metadata:
            self._options.cb_crop.setChecked(False)
            return

        if enabled:
            video_display = self._player.video_display
            dx, dy, dw, dh = video_display.get_display_rect()

            self._crop_overlay = CropOverlay(
                video_display,
                self._metadata.width,
                self._metadata.height,
            )
            self._crop_overlay.crop_changed.connect(self._on_crop_changed)
            self._crop_overlay.activate(dx, dy, dw, dh)
        else:
            if self._crop_overlay:
                self._crop_overlay.deactivate()
                self._crop_overlay.deleteLater()
                self._crop_overlay = None

    def _on_crop_changed(self, x: int, y: int, w: int, h: int):
        pass

    # ===== エクスポート =====

    def _save(self, output_format: str):
        if not self._metadata:
            return

        meta = self._metadata

        options = ExportOptions(
            reverse=self._options.reverse,
            boomerang=self._options.boomerang,
            trim_start=self._player.seekbar.get_a_time(),
            trim_end=self._player.seekbar.get_b_time(),
            quality=self._options.quality,
            watermark=not self._licensed,
        )

        if self._options.crop_enabled and self._crop_overlay:
            options.crop = self._crop_overlay.get_crop_rect()

        is_full_range = (
            options.trim_start <= 0.01
            and abs(options.trim_end - meta.duration) <= 0.01
        )
        no_operations = (
            not options.reverse
            and not options.boomerang
            and options.crop is None
        )
        same_format = (
            (meta.is_gif and output_format == "gif")
            or (not meta.is_gif and output_format == "mp4")
        )

        if is_full_range and no_operations and same_format:
            QMessageBox.information(
                self,
                tr("info_no_operation_title"),
                tr("info_no_operation_msg"),
            )
            return

        ab_duration = options.trim_end - options.trim_start
        if (options.reverse or options.boomerang) and ab_duration > 300:
            result = QMessageBox.question(
                self,
                tr("warn_memory_title"),
                tr("warn_memory_msg", duration=ab_duration),
            )
            if result != QMessageBox.StandardButton.Yes:
                return

        output_path = generate_output_path(meta.filepath, options)
        base_no_ext = os.path.splitext(output_path)[0]
        output_path = f"{base_no_ext}.{output_format}"
        self._output_path = output_path

        is_output_gif = (output_format == "gif")

        self._engine.stop()
        self._player.update_play_state(False)

        try:
            args = build_export_args(
                meta.filepath, output_path, options, is_output_gif, meta.duration,
                video_width=meta.width,
            )
        except Exception as e:
            QMessageBox.critical(self, tr("err_command_title"), tr("err_command_msg", error=str(e)))
            return

        self._options.show_progress()
        self._options.set_enabled(False)

        thread = threading.Thread(
            target=self._export_worker,
            args=(args, ab_duration),
            daemon=True,
        )
        thread.start()

    def _export_worker(self, args: list[str], duration: float):
        try:
            self._ffmpeg.run(
                args,
                progress_callback=lambda p: self._bridge.progress_updated.emit(p),
                duration=duration,
            )
            self._bridge.export_done.emit()
        except CancelledError:
            self._bridge.export_cancelled.emit()
        except (FFmpegError, Exception) as e:
            self._bridge.export_error.emit(str(e))

    def _on_progress(self, ratio: float):
        self._options.update_progress(ratio)

    def _export_done(self):
        self._options.hide_progress()
        self._options.set_enabled(True)
        if self._output_path:
            self._options.show_output_path(self._output_path)
            msg = tr("export_done_msg", filename=os.path.basename(self._output_path))
            if not self._licensed:
                msg += tr("export_done_free_suffix")
            QMessageBox.information(self, tr("export_done_title"), msg)

    def _export_cancelled(self):
        self._options.hide_progress()
        self._options.set_enabled(True)
        if self._output_path and os.path.exists(self._output_path):
            try:
                os.remove(self._output_path)
            except Exception:
                pass

    def _export_error(self, error_msg: str):
        self._options.hide_progress()
        self._options.set_enabled(True)
        QMessageBox.critical(self, tr("err_export_title"), error_msg[:500])

    def _cancel_export(self):
        self._ffmpeg.cancel()

    def _open_output_folder(self):
        if self._output_path:
            folder = os.path.dirname(self._output_path)
            if os.path.isdir(folder):
                os.startfile(folder)

    # ===== FFmpeg ダウンロード =====

    def _offer_ffmpeg_download(self) -> bool:
        """FFmpeg が見つからない場合にダウンロードを提案する。

        Returns:
            True: ダウンロード成功
            False: ユーザーが拒否またはダウンロード失敗
        """
        result = QMessageBox.question(
            self,
            tr("ffmpeg_not_found_title"),
            tr("ffmpeg_not_found_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return False

        progress = QProgressDialog(
            tr("ffmpeg_downloading", pct=0),
            tr("ffmpeg_download_cancel"),
            0,
            100,
            self,
        )
        progress.setWindowTitle(tr("ffmpeg_download_title"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)

        self._download_cancelled = False

        def on_progress(ratio: float):
            if progress.wasCanceled():
                self._download_cancelled = True
                return
            progress.setValue(int(ratio * 100))
            if ratio < 0.9:
                progress.setLabelText(
                    tr("ffmpeg_downloading", pct=int(ratio / 0.9 * 100))
                )
            else:
                progress.setLabelText(tr("ffmpeg_extracting"))

        try:
            download_ffmpeg(progress_callback=on_progress)
        except RuntimeError as e:
            progress.close()
            if self._download_cancelled:
                return False
            QMessageBox.critical(
                self,
                tr("ffmpeg_download_error_title"),
                tr("ffmpeg_download_error_msg", error=str(e)),
            )
            return False

        progress.close()

        if self._download_cancelled:
            return False

        if not is_ffmpeg_available():
            QMessageBox.critical(
                self,
                tr("err_command_title"),
                tr("ffmpeg_extract_error_msg"),
            )
            return False

        return True
