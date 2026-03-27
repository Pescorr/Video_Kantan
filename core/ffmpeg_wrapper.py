"""FFmpeg subprocess実行基盤"""

import os
import sys
import re
import subprocess
import threading
from typing import Callable, Optional


class FFmpegWrapper:
    """FFmpeg/ffprobeのパス解決とsubprocess実行を一元管理"""

    def __init__(self):
        self._base_dir = self._get_base_dir()
        self.ffmpeg_path = self._find_binary("ffmpeg")
        self.ffprobe_path = self._find_binary("ffprobe")
        self._current_process: Optional[subprocess.Popen] = None
        self._cancelled = False

    @staticmethod
    def _get_base_dir() -> str:
        """PyInstaller frozen時とdev時のベースディレクトリを解決"""
        if getattr(sys, 'frozen', False):
            return sys._MEIPASS
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def _find_binary(self, name: str) -> str:
        """ffmpeg/ffprobeバイナリのパスを解決

        検索順序:
        1. 同梱バイナリ（PyInstaller frozen時）
        2. %LOCALAPPDATA%/VideoKantan/ffmpeg/（自動ダウンロード先）
        3. システム PATH
        """
        # 1. 同梱バイナリを優先（PyInstaller frozen時）
        bundled = os.path.join(self._base_dir, "ffmpeg", f"{name}.exe")
        if os.path.isfile(bundled):
            return bundled
        # 2. 自動ダウンロード先
        from core.ffmpeg_downloader import get_ffmpeg_dir
        downloaded = os.path.join(get_ffmpeg_dir(), f"{name}.exe")
        if os.path.isfile(downloaded):
            return downloaded
        # 3. PATHから探す
        import shutil
        found = shutil.which(name)
        if found:
            return found
        raise FileNotFoundError(
            f"{name}が見つかりません。"
        )

    def _get_startupinfo(self) -> Optional[subprocess.STARTUPINFO]:
        """Windows: コンソールウィンドウを非表示にする"""
        if sys.platform == "win32":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE
            return si
        return None

    def run(
        self,
        args: list[str],
        progress_callback: Optional[Callable[[float], None]] = None,
        duration: Optional[float] = None,
    ) -> subprocess.CompletedProcess:
        """FFmpegコマンドを実行（エクスポート用）

        Args:
            args: FFmpegコマンド引数（ffmpegパスは自動付与）
            progress_callback: 進捗コールバック(0.0〜1.0)
            duration: 元動画の長さ（秒）。進捗計算に使用
        """
        self._cancelled = False
        full_args = [self.ffmpeg_path, "-y"] + args

        process = subprocess.Popen(
            full_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=self._get_startupinfo(),
        )
        self._current_process = process

        # stderrから進捗を読み取り
        time_pattern = re.compile(r"time=(\d+):(\d+):(\d+)\.(\d+)")
        stderr_output = []

        for line in iter(process.stderr.readline, b""):
            if self._cancelled:
                process.kill()
                break
            decoded = line.decode("utf-8", errors="replace")
            stderr_output.append(decoded)

            if progress_callback and duration and duration > 0:
                match = time_pattern.search(decoded)
                if match:
                    h, m, s, cs = match.groups()
                    current_time = int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100
                    progress = min(current_time / duration, 1.0)
                    progress_callback(progress)

        process.wait()
        self._current_process = None

        if self._cancelled:
            raise CancelledError("処理がキャンセルされました")

        if process.returncode != 0:
            stderr_text = "".join(stderr_output)
            raise FFmpegError(
                f"FFmpegエラー (code {process.returncode}): {stderr_text[-500:]}"
            )

        if progress_callback:
            progress_callback(1.0)

        return subprocess.CompletedProcess(
            full_args, process.returncode,
            stdout=process.stdout.read() if process.stdout else b"",
            stderr="".join(stderr_output),
        )

    def run_pipe(self, args: list[str]) -> subprocess.Popen:
        """FFmpegをpipeモードで起動（再生用）

        stdout=PIPEでフレームデータを読み取る。
        呼び出し側がstdoutからrawvideoデータを読み取る。
        """
        full_args = [self.ffmpeg_path] + args

        process = subprocess.Popen(
            full_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            startupinfo=self._get_startupinfo(),
        )
        self._current_process = process
        return process

    def run_ffprobe(self, args: list[str]) -> str:
        """ffprobeコマンドを実行して結果を返す"""
        full_args = [self.ffprobe_path] + args

        result = subprocess.run(
            full_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=self._get_startupinfo(),
            timeout=30,
        )

        if result.returncode != 0:
            raise FFmpegError(
                f"ffprobeエラー: {result.stderr.decode('utf-8', errors='replace')[-500:]}"
            )

        return result.stdout.decode("utf-8", errors="replace")

    def cancel(self):
        """実行中のFFmpegプロセスをキャンセル"""
        self._cancelled = True
        if self._current_process and self._current_process.poll() is None:
            self._current_process.kill()


class FFmpegError(Exception):
    """FFmpeg実行エラー"""
    pass


class CancelledError(Exception):
    """処理キャンセル"""
    pass
