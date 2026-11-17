"""DXA cho người dùng không biết IT: bấm đúp DXA.exe là chạy.

Gói DXA.exe (dựng bằng PyInstaller trên GitHub Actions) đã có sẵn Python và mọi thư viện.
File này làm 4 việc:
  1. Hỏi Gemini API key nếu chưa có (lưu vào file .env cạnh DXA.exe).
  2. Dựng kho tri thức (vài giây).
  3. Dựng vector Gemini nếu có key; lỗi thì chạy bản offline.
  4. Bật máy chủ và tự mở trình duyệt.

Chạy từ mã nguồn cũng được:  python dxa_app.py
"""
import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
BASE = Path(sys.executable).parent if FROZEN else Path(__file__).parent  # thư mục người dùng thấy
ENV = BASE / ".env"


def setup_console():
    if os.name == "nt":
        # Lệnh cố định của Windows, không có dữ liệu người dùng
        os.system("chcp 65001 >nul")  # noqa: S605, S607
        os.system("title DXA - Tro ly sua xe may")  # noqa: S605, S607
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def read_key():
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("GEMINI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def ask_key():
    print()
    print("Chưa có Gemini API key.")
    print("  Lấy key miễn phí tại https://aistudio.google.com/apikey")
    print("  Dán key rồi bấm Enter. Bỏ trống rồi bấm Enter để chạy bản offline (lần sau sẽ hỏi lại).")
    try:
        key = input("Gemini API key: ").strip()
    except EOFError:  # chạy không có bàn phím (ví dụ khi kiểm thử tự động)
        key = ""
    if key:
        ENV.write_text(f"GEMINI_API_KEY={key}\n", encoding="utf-8")
        print("Đã lưu key. Lần sau không hỏi nữa.")
    return key


def free_port(start=8000):
    for port in range(start, start + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def main():
    setup_console()
    print("=" * 56)
    print(" DXA - Trợ lý sửa xe máy từ video kênh y dang")
    print("=" * 56)

    key = read_key() or ask_key()
    if key:
        os.environ["GEMINI_API_KEY"] = key

    print("\n[1/3] Dựng kho tri thức...")
    import dxa
    dxa.build()

    import gemini_client as G
    if G.available():
        print("[2/3] Dựng vector Gemini...")
        try:
            import build_gemini
            build_gemini.main()
        except Exception as e:
            print(f"      Không dựng được Gemini ({e.__class__.__name__}). Chạy bản offline.")
    else:
        print("[2/3] Chưa có key: chạy bản offline.")

    import uvicorn
    import api

    port = free_port()
    url = f"http://localhost:{port}"
    print(f"[3/3] DXA đang chạy tại {url}")
    print("      Đóng cửa sổ này là tắt DXA.\n")
    if not os.getenv("DXA_NO_BROWSER"):
        threading.Thread(target=lambda: (time.sleep(2), webbrowser.open(url)), daemon=True).start()
    uvicorn.run(api.app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        traceback.print_exc()
        print("\nCó lỗi. Chụp màn hình cửa sổ này gửi cho người hỗ trợ.")
        try:
            input("Bấm Enter để đóng...")
        except EOFError:
            pass
        sys.exit(1)
