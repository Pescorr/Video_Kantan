"""FFmpeg 自動ダウンローダー

初回起動時に FFmpeg essentials ビルドをダウンロード・展開する。
ダウンロード先: %LOCALAPPDATA%/VideoKantan/ffmpeg/
"""

import os
import io
import zipfile
import urllib.request
from typing import Callable, Optional

# gyan.dev の FFmpeg essentials ビルド (release-build, ~30-40MB)
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

def get_ffmpeg_dir() -> str:
    """FFmpeg ダウンロード先ディレクトリを返す"""
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if not local_app_data:
        local_app_data = os.path.expanduser("~\\AppData\\Local")
    return os.path.join(local_app_data, "VideoKantan", "ffmpeg")


def is_ffmpeg_available() -> bool:
    """ダウンロード済みの FFmpeg が利用可能か確認"""
    ffmpeg_dir = get_ffmpeg_dir()
    ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    ffprobe_exe = os.path.join(ffmpeg_dir, "ffprobe.exe")
    return os.path.isfile(ffmpeg_exe) and os.path.isfile(ffprobe_exe)


def download_ffmpeg(
    progress_callback: Optional[Callable[[float], None]] = None,
) -> str:
    """FFmpeg essentials をダウンロードして展開する。

    Args:
        progress_callback: 進捗コールバック (0.0〜1.0)。
            0.0〜0.9 がダウンロード、0.9〜1.0 が展開。

    Returns:
        FFmpeg バイナリが配置されたディレクトリパス

    Raises:
        RuntimeError: ダウンロードまたは展開に失敗した場合
    """
    ffmpeg_dir = get_ffmpeg_dir()
    os.makedirs(ffmpeg_dir, exist_ok=True)

    try:
        # ダウンロード
        req = urllib.request.Request(
            FFMPEG_URL,
            headers={"User-Agent": "VideoKantan/1.0.0"},
        )
        response = urllib.request.urlopen(req, timeout=120)

        content_length = response.headers.get("Content-Length")
        total_size = int(content_length) if content_length else 0

        buffer = io.BytesIO()
        downloaded = 0
        chunk_size = 256 * 1024  # 256KB

        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            buffer.write(chunk)
            downloaded += len(chunk)

            if progress_callback and total_size > 0:
                # ダウンロード進捗: 0.0 〜 0.9
                progress_callback(min(downloaded / total_size * 0.9, 0.9))

        if progress_callback:
            progress_callback(0.9)

        # ZIP 展開
        buffer.seek(0)
        with zipfile.ZipFile(buffer) as zf:
            # ZIP 内の ffmpeg.exe と ffprobe.exe を探す
            ffmpeg_found = False
            ffprobe_found = False

            for info in zf.infolist():
                basename = os.path.basename(info.filename)
                if basename == "ffmpeg.exe":
                    _extract_single(zf, info, ffmpeg_dir, "ffmpeg.exe")
                    ffmpeg_found = True
                elif basename == "ffprobe.exe":
                    _extract_single(zf, info, ffmpeg_dir, "ffprobe.exe")
                    ffprobe_found = True

                if ffmpeg_found and ffprobe_found:
                    break

            if not ffmpeg_found or not ffprobe_found:
                raise RuntimeError(
                    "ダウンロードした ZIP に ffmpeg.exe / ffprobe.exe が見つかりません。"
                )

        if progress_callback:
            progress_callback(1.0)

        return ffmpeg_dir

    except zipfile.BadZipFile:
        raise RuntimeError("ダウンロードしたファイルが破損しています。再試行してください。")
    except urllib.error.URLError as e:
        raise RuntimeError(f"ダウンロードに失敗しました: {e}")
    except OSError as e:
        raise RuntimeError(f"ファイル展開に失敗しました: {e}")


def _extract_single(
    zf: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    dest_dir: str,
    dest_name: str,
) -> None:
    """ZIP 内の単一ファイルを指定名で展開する"""
    dest_path = os.path.join(dest_dir, dest_name)
    with zf.open(info) as src, open(dest_path, "wb") as dst:
        while True:
            chunk = src.read(256 * 1024)
            if not chunk:
                break
            dst.write(chunk)
