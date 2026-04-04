import base64
import mimetypes
import os
import subprocess
import tempfile
import time
from typing import Tuple, Optional
from urllib.parse import urlparse
import requests
from analysis_video.config.settings import Base64Limits
from .logger import get_logger

logger = get_logger("utils.video_base64")
DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "video_downloads"))

def _encode_to_base64(data: bytes, mime: Optional[str] = None, include_data_uri: bool = False) -> str:
    """将字节数据编码为 Base64 字符串。

    Args:
        data (bytes): 待编码的字节。
        mime (Optional[str], optional): 数据的 MIME 类型，用于构建 Data URI。 Defaults to None.
        include_data_uri (bool, optional): 是否在结果中包含 Data URI 前缀 (e.g., 'data:video/mp4;base64,')。 Defaults to False.

    Returns:
        str: Base64 编码后的字符串。
    """
    b64 = base64.b64encode(data).decode("utf-8")
    if include_data_uri:
        mime = mime or "application/octet-stream"
        return f"data:{mime};base64,{b64}"
    return b64


def _extract_audio_from_file(input_path: str) -> Tuple[bytes, str]:
    """使用 ffmpeg 从视频文件中分离音轨。先尝试m4a格式，不行就试试mp3格式。

    该函数首先尝试无损拷贝音轨到 m4a 格式（适用于 AAC 编码）。
    如果失败，则回退到将音轨编码为 128k 的 mp3。

    Args:
        input_path (str): 输入的视频文件路径。

    Raises:
        RuntimeError: 如果 ffmpeg 未安装或音轨分离失败。

    Returns:
        Tuple[bytes, str]: 包含音频数据和其 MIME 类型的元组 (audio_bytes, mime)。
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        m4a_out = os.path.join(tmpdir, "audio.m4a")
        mp3_out = os.path.join(tmpdir, "audio.mp3")

        # 优先尝试无损拷贝（适用于 AAC）
        cmd_copy = [
            "ffmpeg", "-y", "-i", input_path, "-vn", "-acodec", "copy", m4a_out
        ]
        try:
            res = subprocess.run(cmd_copy, stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # 让子进程调用ffmpeg 抽音频，别在终端输出，保存在res中
            if res.returncode == 0 and os.path.exists(m4a_out):
                with open(m4a_out, "rb") as f:
                    return f.read(), "audio/mp4"  # m4a 的 MIME
        except FileNotFoundError:
            raise RuntimeError("未检测到 ffmpeg，请先安装后再进行音轨分离。")

        # 回退到 mp3 编码
        cmd_mp3 = [
            "ffmpeg", "-y", "-i", input_path, "-vn", "-acodec", "libmp3lame", "-b:a", "128k", mp3_out
        ]
        res = subprocess.run(cmd_mp3, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0 or not os.path.exists(mp3_out):
            raise RuntimeError("音轨分离失败，请确认视频包含音频或 ffmpeg 正常可用。")

        with open(mp3_out, "rb") as f:
            return f.read(), "audio/mpeg"


def _download_video(url: str, timeout: int = 30, preferred_basename: Optional[str] = None) -> str:
    """下载视频到指定目录并返回路径。"""
    try:
        p = urlparse(url)
        if p.scheme not in {"http", "https"}:
            raise ValueError(f"Invalid http(s) url: {url}")
    except Exception:
        raise ValueError(f"Invalid http(s) url: {url}")

    limits = Base64Limits()
    hard_limit_bytes = limits.hard_limit_bytes

    with requests.get(url, stream=True, timeout=timeout) as resp:
        resp.raise_for_status()
        content_length = resp.headers.get("Content-Length")
        content_type = resp.headers.get("Content-Type") or ""

        if content_length and int(content_length) > hard_limit_bytes:
            raise ValueError(
                f"Remote file too large: {content_length} bytes > {hard_limit_bytes} bytes hard limit"
            )

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        filename = os.path.basename(p.path) or f"video_{int(time.time())}"
        name, ext = os.path.splitext(filename)
        if preferred_basename:
            name = str(preferred_basename)
        if not ext:
            ct = content_type.split(";")[0].strip().lower()
            ext_map = {
                "video/mp4": ".mp4",
                "video/quicktime": ".mov",
                "video/webm": ".webm",
                "video/3gpp": ".3gp",
                "audio/mp4": ".m4a",
                "audio/mpeg": ".mp3",
            }
            ext = ext_map.get(ct, ".mp4")
        filename = name + ext
        filepath = os.path.join(DOWNLOAD_DIR, filename)

        size = 0
        try:
            with open(filepath, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 512):  # 512KB chunks
                    if chunk:
                        size += len(chunk)
                        if size > hard_limit_bytes:
                            raise ValueError(
                                f"Downloaded data exceeded hard limit: {size} bytes > {hard_limit_bytes} bytes"
                            )
                        f.write(chunk)
            return filepath
        except Exception:
            if os.path.exists(filepath):
                os.unlink(filepath)  # 如果下载失败或超限，清理部分下载的文件
            raise


def video_to_base64(
    path_or_url: str,
    include_data_uri: bool = True,
    timeout: int = 30,
    preferred_basename: Optional[str] = None,
) -> str:
    """
    从本地文件路径或 URL 读取视频并将其转换为 Base64 编码，根据大小决定处理策略。

    - 如果输入是 URL，视频将被流式下载到 `video_downloads` 目录进行处理并保留。
    - 如果文件大小小于等于 `encode_limit_bytes`，则编码整个视频。
    - 如果大小介于 `encode_limit_bytes` 和 `hard_limit_bytes` 之间，则仅提取并编码其音轨。
    - 如果文件大小超过 `hard_limit_bytes`，将抛出异常。

    Args:
        path_or_url (str): 视频文件的本地路径或 URL。
        include_data_uri (bool): 是否在返回的字符串中包含 data URI 头部。
        timeout (int): 下载请求的超时时间（秒）。

    Raises:
        FileNotFoundError: 如果指定路径的文件不存在。
        ValueError: 如果 URL 无效、下载失败、或文件大小超过 `hard_limit_bytes`。
        requests.exceptions.RequestException: 如果发生网络请求错误。

    Returns:
        str: 视频或其音轨的 Base64 编码字符串。
    """
    is_url = urlparse(path_or_url).scheme in {"http", "https"}

    if is_url:
        path = _download_video(path_or_url, timeout=timeout, preferred_basename=preferred_basename)
    else:
        path = path_or_url

    # --- 文件处理逻辑 ---
    limits = Base64Limits()
    hard_limit_bytes = limits.hard_limit_bytes
    encode_limit_bytes = limits.encode_limit_bytes

    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")

    size = os.path.getsize(path)
    if size > hard_limit_bytes:
        raise ValueError(f"File too large: {size} bytes > {hard_limit_bytes} bytes hard limit")

    if size <= encode_limit_bytes:
        with open(path, "rb") as f:
            data = f.read()
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if mime == "application/octet-stream":
            header = data[:16]
            if b"ftyp" in header:
                mime = "video/mp4"
        logger.info(f"Encoding video to base64, size={size} bytes, mime={mime}")
        return _encode_to_base64(data, mime=mime, include_data_uri=include_data_uri)
    else:
        audio_bytes, audio_mime = _extract_audio_from_file(path)
        logger.info(
            f"Extracted audio from video, video_size={size} bytes, audio_size={len(audio_bytes)} bytes, mime={audio_mime}"
        )
        return _encode_to_base64(audio_bytes, mime=audio_mime, include_data_uri=include_data_uri)