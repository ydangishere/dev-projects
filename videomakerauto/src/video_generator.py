"""Step 3 & 4: Tạo video từ script + ghép với audio bằng MoviePy."""
from pathlib import Path
from typing import List

import numpy as np
from moviepy.editor import (
    ColorClip,
    ImageClip,
    TextClip,
    CompositeVideoClip,
    AudioFileClip,
    concatenate_videoclips,
)

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
_USE_PIL_FALLBACK = False  # Set True khi TextClip lỗi (không có ImageMagick)


def _text_to_image_pil(line: str, size: tuple = (1080, 200)) -> np.ndarray:
    """Tạo ảnh text bằng Pillow (fallback khi không có ImageMagick)."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    x, y = 50, (size[1] - 40) // 2  # vị trí gần center
    draw.text((x, y), line[:60], fill="white", font=font)  # giới hạn 60 ký tự
    return np.array(img)


def _create_text_clip(line: str, seg_duration: float):
    """Tạo clip text, fallback sang Pillow nếu TextClip lỗi."""
    global _USE_PIL_FALLBACK
    if not _USE_PIL_FALLBACK:
        try:
            txt = TextClip(txt=line, fontsize=36, color="white", font="Arial")
            return txt.set_duration(seg_duration).set_position("center")
        except Exception:
            _USE_PIL_FALLBACK = True
    arr = _text_to_image_pil(line)
    txt = ImageClip(arr).set_duration(seg_duration).set_position("center")
    return txt


def _split_script(script: str, max_chars: int = 50) -> List[str]:
    """Chia script thành các dòng ngắn để hiển thị."""
    words = script.split()
    lines = []
    current = []
    length = 0
    for w in words:
        if length + len(w) + 1 > max_chars and current:
            lines.append(" ".join(current))
            current = [w]
            length = len(w)
        else:
            current.append(w)
            length += len(w) + 1 if current else len(w)
    if current:
        lines.append(" ".join(current))
    return lines


def create_video_from_script(script: str, duration: float):
    """Tạo video nền đen + text từ script (phân bổ theo duration)."""
    lines = _split_script(script)
    if not lines:
        lines = [script[:80]]

    seg_duration = duration / len(lines)
    clips = []

    for line in lines:
        txt = _create_text_clip(line, seg_duration)
        bg = ColorClip(size=(1080, 1920), color=(0, 0, 0), duration=seg_duration)
        comp = CompositeVideoClip([bg, txt])
        clips.append(comp)

    return concatenate_videoclips(clips)


def generate_video(script: str, audio_path: Path, output_name: str = "output.mp4") -> Path:
    """Tạo video: nền đen + text theo script, ghép với audio."""
    audio = AudioFileClip(str(audio_path))
    duration = audio.duration

    video = create_video_from_script(script, duration)
    video = video.set_audio(audio)

    out_path = OUTPUT_DIR / output_name
    video.write_videofile(str(out_path), fps=24, codec="libx264", audio_codec="aac")
    video.close()
    audio.close()
    return out_path
