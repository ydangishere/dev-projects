# DXA (bản Dana) – Hỏi thợ sửa xe máy

Bản này giống DXA thường, nhưng phần trả lời câu hỏi do agent viết bằng [Dana](https://github.com/aitomatic/dana) đảm nhận (`dxa_agent.na`).

## Chạy DXA

1. Tải repo về: trên GitHub bấm **Code → Download ZIP**, giải nén.
2. Mở thư mục `dxa-automative-agent_dana`, bấm đúp **`run.bat`**.
3. Lần đầu: bấm **Y** nếu được hỏi cài Python, rồi chờ cài thư viện (5–10 phút).
4. Dán Gemini API key rồi bấm Enter (hoặc bấm Enter để bỏ qua).
5. Trình duyệt tự mở DXA. Gõ câu hỏi, bấm **Hỏi thợ**.

## DXA làm gì, nhìn một lần

Video → phụ đề → LLM rút ra case → bộ kiểm chống bịa → thợ duyệt → kho tri thức → agent → câu chưa trả lời được → thợ bổ sung kiến thức trên tab riêng → kho tri thức.

DXA là **một trang, hai tab** (`localhost:8000`):

- **Tab "Hỏi"** (mọi người): khách hỏi bệnh xe, xem câu trả lời kèm nguồn video.
- **Tab "Bổ sung kiến thức"** (chỉ thợ): bấm **Đăng nhập thợ**, nhập mã thợ, tab này mới hiện ra. Thợ xem câu chưa trả lời được, nhập kiến thức (triệu chứng, nguyên nhân, cách sửa, thông số), bấm **Lưu** thì kho dựng lại ngay, rồi bấm **Chạy thử lại câu hỏi**.

Mã thợ của bản chạy thử là **`1234`**. Dùng thật thì đổi mã bằng dòng `DXA_THO_CODE=...` trong file `.env`.
Quyền được **máy chủ** kiểm: không đăng nhập thợ thì gọi thẳng API lưu kiến thức cũng bị chặn (lỗi 401).

![Pipeline DXA: từ video đến agent, câu chưa trả lời được quay lại cho thợ](docs/pipeline.png)

## DXA so với một "Digital Engineer"

|  | DXA hiện tại | Digital Engineer |
|---|:---:|:---:|
| Kiến thức chuyên gia | ✅ | ✅ |
| Kiểm soát, có người duyệt | ✅ | ✅ |
| Suy luận nhiều bước để chẩn đoán | ❌ | ✅ |
| Dùng dữ liệu thật (cảm biến, ảnh) | ❌ | ✅ |

## Luồng chạy khi bấm run.bat

![Luồng chạy khi bấm run.bat](docs/run-flow.png)

## Các bước dựng DXA

![Các bước dựng DXA](docs/flow.png)

## Kiến trúc DXA (bản Dana)

![Kiến trúc DXA bản Dana](docs/architecture.png)
