"""ffprobeでメタデータ取得 + 単フレーム抽出"""

import io
import json
from dataclasses import dataclass
from typing import Optional

from PIL import Image

from core.ffmpeg_wrapper import FFmpegWrapper


@dataclass
class VideoMetadata:
    """動画メタデータ"""
    width: int
    height: int
    duration: float  # 秒
    fps: float
    n_frames: int
    codec: str
    is_gif: bool
    filepath: str


def get_metadata(ffmpeg: FFmpegWrapper, filepath: str) -> VideoMetadata:
    """ffprobeで動画メタデータを取得"""
    output = ffmpeg.run_ffprobe([
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        filepath,
    ])

    data = json.loads(output)

    # 動画ストリームを探す
    video_stream = None
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        raise ValueError("動画ストリームが見つかりません")

    width = int(video_stream.get("width", 0))
    height = int(video_stream.get("height", 0))
    codec = video_stream.get("codec_name", "unknown")
    is_gif = codec == "gif" or filepath.lower().endswith(".gif")

    # FPS取得
    fps = _parse_fps(video_stream.get("r_frame_rate", "30/1"))
    if fps <= 0:
        fps = _parse_fps(video_stream.get("avg_frame_rate", "30/1"))
    if fps <= 0:
        fps = 30.0

    # 再生時間取得
    duration = 0.0
    if "duration" in video_stream:
        duration = float(video_stream["duration"])
    elif "duration" in data.get("format", {}):
        duration = float(data["format"]["duration"])

    # フレーム数
    n_frames = int(video_stream.get("nb_frames", 0))
    if n_frames <= 0 and duration > 0 and fps > 0:
        n_frames = int(duration * fps)

    return VideoMetadata(
        width=width,
        height=height,
        duration=duration,
        fps=fps,
        n_frames=max(n_frames, 1),
        codec=codec,
        is_gif=is_gif,
        filepath=filepath,
    )


def extract_frame(
    ffmpeg: FFmpegWrapper,
    filepath: str,
    timestamp: float,
    width: int,
    height: int,
) -> Optional[Image.Image]:
    """指定時刻のフレームをPIL Imageとして取得

    Args:
        filepath: 動画ファイルパス
        timestamp: 秒単位のタイムスタンプ
        width: 動画の幅
        height: 動画の高さ
    """
    args = [
        "-ss", f"{timestamp:.3f}",
        "-i", filepath,
        "-frames:v", "1",
        "-f", "image2pipe",
        "-vcodec", "png",
        "pipe:1",
    ]

    try:
        process = ffmpeg.run_pipe(args)
        data = process.stdout.read()
        process.wait()

        if data:
            return Image.open(io.BytesIO(data))
    except Exception:
        pass

    return None


def _parse_fps(fps_str: str) -> float:
    """FPS文字列（例: "30/1", "29.97"）をfloatに変換"""
    try:
        if "/" in fps_str:
            num, den = fps_str.split("/")
            den_val = float(den)
            if den_val == 0:
                return 0.0
            return float(num) / den_val
        return float(fps_str)
    except (ValueError, ZeroDivisionError):
        return 0.0
