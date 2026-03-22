# AI Video Maker Auto

Pipeline tự động tạo video từ ý tưởng: đưa topic vào → AI viết script → tạo giọng đọc → ghép thành video MP4.

---

## 1. Yêu cầu

- Windows 10/11
- Python 3.8 trở lên
- Tài khoản OpenAI (có API key)
- Tài khoản ElevenLabs (có API key)

---

## 2. Cài đặt từng bước

### Bước 2.1: Kiểm tra Python

Mở PowerShell, chạy:

```powershell
python --version
```

Nếu hiện `Python 3.8.x` trở lên là dùng được. Nếu chưa có Python, tải tại: https://www.python.org/downloads/

### Bước 2.2: Vào thư mục project

```powershell
cd "d:\dev project\videomakerauto"
```

### Bước 2.3: Cài thư viện

```powershell
pip install -r requirements.txt
```

Chờ cài xong (khoảng 1–2 phút). Các thư viện: OpenAI, ElevenLabs, MoviePy, python-dotenv.

---

## 3. Lấy API keys

### Bước 3.1: OpenAI API key

1. Vào https://platform.openai.com/
2. Đăng nhập hoặc đăng ký
3. Vào **API keys** → **Create new secret key**
4. Copy key (bắt đầu bằng `sk-`), lưu lại vì chỉ hiện một lần

### Bước 3.2: ElevenLabs API key

1. Vào https://elevenlabs.io/
2. Đăng nhập hoặc đăng ký
3. Vào **Profile** → **API Key** → **Copy** hoặc tạo key mới

### Bước 3.3: Voice ID (tùy chọn)

Mặc định dùng giọng Rachel. Muốn đổi:

1. Vào https://elevenlabs.io/voice-library
2. Chọn giọng → mở tab **API** → copy **Voice ID**

---

## 4. Cấu hình file .env

### Bước 4.1: Mở file .env

Trong thư mục project có file `.env`. Mở bằng Notepad hoặc VS Code.

### Bước 4.2: Điền API keys

Sửa các dòng sau bằng key thật:

```
OPENAI_API_KEY=sk-proj-xxxx (thay bằng key OpenAI của bạn)
ELEVENLABS_API_KEY=xxxx (thay bằng key ElevenLabs của bạn)
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM (có thể giữ hoặc đổi voice khác)
```

Lưu file.

---

## 5. Chạy pipeline

### Bước 5.1: Vào thư mục project

```powershell
cd "d:\dev project\videomakerauto"
```

### Bước 5.2: Chạy lệnh

**Cách 1 – Dùng topic mặc định ("make money with AI"):**

```powershell
python main.py
```

**Cách 2 – Nhập topic của bạn:**

```powershell
python main.py "cách kiếm tiền từ TikTok"
```

**Cách 3 – Topic khác:**

```powershell
python main.py "bí quyết giảm cân nhanh"
python main.py "học lập trình cho người mới bắt đầu"
```

### Bước 5.3: Đợi kết quả

Pipeline chạy lần lượt:

1. **Generating script...** – GPT viết nội dung
2. **Generating voice...** – ElevenLabs tạo giọng đọc
3. **Generating scenes...** – MoviePy ghép video

Khi xong, dòng cuối sẽ là: `Xong! Video: d:\dev project\videomakerauto\output\xxx.mp4`

### Bước 5.4: Xem video

Mở thư mục `output/`, mở file `.mp4` vừa tạo.

---

## 6. Tùy chọn dòng lệnh

| Tùy chọn        | Ý nghĩa                                      |
|-----------------|-----------------------------------------------|
| `--no-cache`    | Tắt cache, gọi lại API mỗi lần (tốn quota hơn) |

**Ví dụ:**

```powershell
python main.py "chủ đề" --no-cache
```

---

## 7. Cấu trúc project

```
videomakerauto/
├── main.py              # Chạy pipeline
├── requirements.txt     # Danh sách thư viện
├── .env                 # API keys (không commit lên git)
├── .env.example         # Mẫu .env
├── README.md            # File này
├── src/
│   ├── script_generator.py   # Step 1: GPT viết script
│   ├── voice_generator.py    # Step 2: ElevenLabs tạo voice
│   ├── video_generator.py    # Step 3–4: MoviePy ghép video
│   └── cache.py              # Cache script + voice
├── output/              # Video ra đây
└── cache/                # Cache (script, voice) để tái dùng
```

---

## 8. Pipeline hoạt động thế nào

1. **Topic** → Bạn nhập chủ đề (ví dụ: "cách kiếm tiền từ TikTok").
2. **Script** → GPT viết nội dung video (hook, nội dung, CTA).
3. **Voice** → ElevenLabs chuyển script thành file MP3.
4. **Video** → MoviePy ghép nền đen + text theo script với giọng đọc.

Output: video MP4 dạng TikTok/Shorts (1080x1920), nền đen, text hiển thị theo nội dung script.

---

## 9. Lỗi thường gặp

### Lỗi: "OPENAI_API_KEY not found" hoặc "ELEVENLABS_API_KEY not found"

→ Chưa điền API key vào file `.env`, hoặc `.env` không nằm đúng trong thư mục project.

### Lỗi: "Rate limit" hoặc "Quota exceeded"

→ Hết quota API. Chờ hoặc nâng cấp gói OpenAI/ElevenLabs.

### Lỗi liên quan ImageMagick

→ Trên Windows có thể thiếu ImageMagick. Pipeline sẽ tự dùng Pillow thay thế.

### Video không có tiếng hoặc tiếng lạc

→ Kiểm tra file MP3 trong thư mục `output/` hoặc `cache/`. Nếu ElevenLabs lỗi, thử chạy lại với `--no-cache`.

---

## 10. Chi phí gần đúng

- **OpenAI (GPT-4o-mini):** ~0.01–0.05$ mỗi video
- **ElevenLabs:** Theo số ký tự (có free tier)

Cache giúp giảm gọi API khi dùng lại topic/script tương tự.
