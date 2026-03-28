#!/usr/bin/env bash
# ========================================
#  macOS / Linux — mở GUI scan (giống CHAY_SCAN.bat trên Windows).
#  Không cần nhớ main.py.
#
#  Lần đầu: chmod +x CHAY_SCAN.sh
#  Chạy: ./CHAY_SCAN.sh   hoặc kéo thả vào Terminal
# ========================================

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1

if [ -x "$ROOT/.venv/bin/python3" ]; then
  exec "$ROOT/.venv/bin/python3" "$ROOT/app/scan_gui.py"
fi

if [ -f "$ROOT/.venv/bin/python3" ]; then
  exec "$ROOT/.venv/bin/python3" "$ROOT/app/scan_gui.py"
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$ROOT/app/scan_gui.py"
fi

if command -v python >/dev/null 2>&1; then
  exec python "$ROOT/app/scan_gui.py"
fi

echo "Cài Python 3.8+ (python3 trên PATH) hoặc tạo .venv trong thư mục này: python3 -m venv .venv" >&2
exit 1
