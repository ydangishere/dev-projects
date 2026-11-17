# Prompt rút tri thức từ transcript (dùng cho video 11 trở đi)

Gửi cho LLM (Claude / Gemini) từng file `data/clean/<video_id>.txt`, kèm tiêu đề video.

---
Bạn là thợ sửa xe máy lâu năm. Đây là phụ đề đã làm sạch của một video sửa xe, mỗi dòng bắt đầu bằng [giây].

Rút ra mọi chuỗi "Triệu chứng -> Nguyên nhân -> Cách sửa" mà video THỰC SỰ nói. Không tự thêm kiến thức ngoài video.
Trả về JSON đúng schema sau, không giải thích thêm:

{"cases": [{
  "id": "",                  // để trống, script tự đánh số
  "video_id": "<video_id>",
  "t": 0,                    // giây bắt đầu đoạn nói về case này, lấy từ [giây]
  "system": "nhiên liệu | đánh lửa | động cơ | điện | khung sườn | truyền động | phanh | khác",
  "symptom": "triệu chứng, viết theo cách khách hàng tả",
  "cause": "nguyên nhân",
  "fix": "các bước sửa, ngắn gọn",
  "parts": ["phụ tùng"], "tools": ["dụng cụ"], "vehicles": ["dòng xe / loại bình / loại máy"],
  "specs": [{"name": "", "value": "", "unit": ""}],
  "warnings": ["lưu ý an toàn hoặc sai lầm hay gặp"],
  "reviewed": false
}]}

Quy tắc:
- Thông số (mm, độ, dem...) phải chép đúng số trong video; 1 dem = 0.1 mm.
- Nếu phụ đề nghe sai mà không chắc, ghi "[?]" vào chỗ đó thay vì đoán.
- Video chỉ khoe hàng, bán xe, không có kiến thức sửa: trả {"cases": []}.
---
