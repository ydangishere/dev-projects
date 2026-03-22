"""
Chạy pipeline tương tác: nhập API key (nếu chưa có) + topic rồi tạo video.
"""
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
ENV_PATH = PROJECT_ROOT / ".env"


def ensure_env():
    """Nếu chưa có .env thì hỏi API key và tạo."""
    if ENV_PATH.exists():
        return True

    print("\n=== Nhập API keys (chỉ cần 1 lần) ===\n")
    openai = input("OPENAI_API_KEY: ").strip()
    eleven = input("ELEVENLABS_API_KEY: ").strip()
    voice = input("ELEVENLABS_VOICE_ID (Enter = mặc định Rachel): ").strip()

    if not openai or not eleven:
        print("Cần OPENAI_API_KEY và ELEVENLABS_API_KEY.")
        sys.exit(1)

    lines = [
        f"OPENAI_API_KEY={openai}",
        f"ELEVENLABS_API_KEY={eleven}",
        f"ELEVENLABS_VOICE_ID={voice or '21m00Tcm4TlvDq8ikWAM'}",
    ]
    ENV_PATH.write_text("\n".join(lines), encoding="utf-8")
    print("\nĐã lưu .env\n")


def main():
    os.chdir(PROJECT_ROOT)
    ensure_env()

    print("=== AI Video Maker Auto ===\n")
    topic = input("Nhập chủ đề video (Enter = make money with AI): ").strip()
    if not topic:
        topic = "make money with AI"

    print(f"\nĐang tạo video: {topic}\n")
    result = subprocess.run([sys.executable, "main.py", topic], cwd=PROJECT_ROOT)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
