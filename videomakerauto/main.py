"""
Pipeline AI tạo video tự động.
Chạy: python main.py [topic]
"""
import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.script_generator import generate_script
from src.voice_generator import generate_voice
from src.video_generator import generate_video

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

MAX_RETRIES = 3


def retry_on_fail(func, *args, **kwargs):
    """Retry khi API lỗi."""
    for attempt in range(MAX_RETRIES):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            log.warning(f"Lỗi (lần {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt == MAX_RETRIES - 1:
                raise
    return None


def run_pipeline(topic: str, use_cache: bool = True) -> Path:
    """Chạy full pipeline: script → voice → video."""
    log.info("Generating script...")
    script = retry_on_fail(generate_script, topic, use_cache)
    log.info(f"Script: {script[:80]}...")

    log.info("Generating voice...")
    audio_path = retry_on_fail(generate_voice, script, use_cache)
    log.info(f"Voice: {audio_path}")

    log.info("Generating scenes...")
    out_name = f"{topic.replace(' ', '_')[:30]}.mp4"
    video_path = generate_video(script, audio_path, out_name)
    log.info(f"Video: {video_path}")

    return video_path


def main():
    parser = argparse.ArgumentParser(description="AI tạo video tự động")
    parser.add_argument(
        "topic",
        nargs="?",
        default="make money with AI",
        help="Chủ đề video (mặc định: make money with AI)",
    )
    parser.add_argument("--no-cache", action="store_true", help="Tắt cache")
    args = parser.parse_args()

    try:
        path = run_pipeline(args.topic, use_cache=not args.no_cache)
        log.info(f"Xong! Video: {path}")
    except Exception as e:
        log.error(f"Lỗi: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
