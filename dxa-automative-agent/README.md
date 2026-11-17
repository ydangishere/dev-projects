# DXA – Hỏi thợ sửa xe máy

Xe máy của bạn bị gì, cứ gõ hỏi DXA.
DXA trả lời theo kinh nghiệm thợ trong 30 video của kênh YouTube [y dang](https://www.youtube.com/@ydang7076).
Mỗi câu trả lời có nút mở video, nhảy đúng đoạn thợ chỉ cách sửa.

![Giao diện DXA](docs/ui.png)

## Ví dụ bạn có thể hỏi

| Bạn gõ | DXA trả lời |
|---|---|
| Bình xăng con chảy xăng khi dựng xe | Nguyên nhân do phao xăng nằm sai góc, cách chỉnh lại, và mở video tới phút 5:29 |
| buông ga mà ga không về | Các chỗ cần kiểm: ốc ralenti, phao xăng, dây ga, kèm video |
| Côn bị trượt | Cách chỉnh côn và cách thử lại sau khi chỉnh |

Gõ không dấu cũng được.

## Cách dùng (máy Windows)

1. **Tải về:** bấm vào [DXA-Windows.zip](https://github.com/ydangishere/dev-projects/releases/download/dxa-windows/DXA-Windows.zip) để tải.
2. **Giải nén:** bấm chuột phải vào file vừa tải, chọn **Extract All**.
3. **Mở DXA:** vào thư mục `DXA`, bấm đúp **`DXA.exe`**.

Trình duyệt sẽ tự mở trang DXA. Bạn gõ câu hỏi vào ô màu vàng rồi bấm **Hỏi thợ**.

Muốn tắt DXA thì đóng cửa sổ màu đen.

![Các bước khi mở DXA](docs/run-flow.png)

## Lần đầu mở có thể gặp 2 thứ

**1. Windows hiện bảng "Windows protected your PC"**

Bảng này hiện vì DXA là phần mềm mới, chưa đăng ký với Microsoft.
Bấm **More info**, rồi bấm **Run anyway**.
Chỉ cần làm một lần.

**2. Cửa sổ đen hỏi "Gemini API key"**

Key là một mã giúp DXA dùng AI của Google để viết câu trả lời dễ đọc hơn.
Không có key thì DXA vẫn chạy, chỉ là câu trả lời ngắn và khô hơn.

- **Không muốn dùng key:** bấm Enter để bỏ qua.
- **Muốn dùng key (miễn phí):** vào [aistudio.google.com/apikey](https://aistudio.google.com/apikey), đăng nhập Gmail, bấm **Create API key**, copy mã đó, dán vào cửa sổ đen rồi bấm Enter.

Dán key một lần là DXA nhớ, lần sau không hỏi nữa.

## Hỏi sao cho DXA trả lời đúng

- **Tả triệu chứng xe,** ví dụ "xe đề lâu không nổ", "bugi cháy đen".
- **Mỗi lần hỏi một bệnh.**
- DXA báo **"Chưa có trong video"** nghĩa là 30 video chưa nói tới bệnh đó. DXA không đoán bừa.

## Cần biết trước khi sửa xe

- DXA chỉ biết những gì thợ nói trong 30 video.
- Các câu trả lời chưa được thợ kiểm tra kỹ.
- Vì vậy, **luôn bấm xem video** trước khi tự tay sửa xe.

## Hỏi đáp nhanh

**Có tốn tiền không?**
Không. DXA miễn phí. Key Gemini cũng có gói miễn phí.

**Có cần mạng không?**
Có mạng thì xem được video. Không có mạng thì DXA vẫn trả lời bằng chữ.

**Máy Mac dùng được không?**
Hiện chỉ có bản Windows. Máy Mac cần người làm kỹ thuật cài giúp.

**Muốn đổi key thì sao?**
Mở file `.env` trong thư mục `DXA` bằng Notepad, sửa dòng `GEMINI_API_KEY=`.

---

Người làm kỹ thuật (cài từ mã nguồn, cách hoạt động, kiểm thử): xem [docs/KY-THUAT.md](docs/KY-THUAT.md).
