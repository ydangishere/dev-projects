#!/usr/bin/env bash
# DXA - Trợ lý sửa xe máy. macOS: bấm đúp file này. Linux: chạy ./run.command
# Lần đầu: tự cài thư viện (vài phút), hỏi Gemini API key. Những lần sau: mở trình duyệt sau vài giây.
set -e
cd "$(dirname "$0")"
export PYTHONUTF8=1

loi() { echo; echo "[DXA] Có lỗi ở bước trên. Chụp màn hình cửa sổ này gửi cho người hỗ trợ."; read -r -p "Bấm Enter để đóng..." _; exit 1; }
trap loi ERR

# 1. Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "[DXA] Máy chưa có Python 3. Cài tại https://www.python.org/downloads/ rồi bấm lại file này."
  read -r -p "Bấm Enter để đóng..." _; exit 1
fi

# 2. Môi trường riêng + thư viện (chỉ làm lần đầu)
if [ ! -x .venv/bin/python ]; then
  echo "[DXA] Tạo môi trường Python riêng cho DXA..."
  python3 -m venv .venv
fi
VPY=.venv/bin/python
if [ ! -f .venv/da_cai.txt ]; then
  echo "[DXA] Đang cài thư viện, lần đầu mất vài phút..."
  "$VPY" -m pip install --upgrade pip -q
  "$VPY" -m pip install -r requirements.txt -q
  echo ok > .venv/da_cai.txt
fi

# 3. Gemini API key: còn thiếu key thì lần nào cũng hỏi
if ! grep -qE '^GEMINI_API_KEY=.+' .env 2>/dev/null; then
  echo
  echo "[DXA] Chưa có Gemini API key. Dán key rồi bấm Enter (lấy miễn phí tại https://aistudio.google.com/apikey)."
  echo "      Bỏ trống rồi bấm Enter để chạy bản offline, lần sau sẽ hỏi lại."
  read -r -p "Gemini API key: " KEY
  if [ -n "$KEY" ]; then echo "GEMINI_API_KEY=$KEY" > .env; fi
fi

# 4. Dựng kho tri thức
echo "[DXA] Dựng kho tri thức..."
"$VPY" dxa.py build
"$VPY" build_gemini.py 2>/dev/null || echo "[DXA] Chưa dựng Gemini: chạy bản offline. Sửa key trong file .env nếu cần."

# 5. Chạy máy chủ và mở trình duyệt
echo
echo "[DXA] Đang chạy tại http://localhost:8000. Đóng cửa sổ này để tắt DXA."
( sleep 5; (command -v open >/dev/null && open http://localhost:8000) || xdg-open http://localhost:8000 >/dev/null 2>&1 || true ) &
trap - ERR
"$VPY" -m uvicorn api:app --port 8000
