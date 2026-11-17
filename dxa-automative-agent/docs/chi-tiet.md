# DXA – Trợ lý sửa xe máy từ kênh YouTube "y dang"

Đã nạp **đủ 30/30 video** của kênh https://www.youtube.com/@ydang7076.

## Số liệu

| | |
|---|---|
| Video | 30 (27 có nội dung, 3 bỏ qua: "Đồ ve chai", "PE24 unbox", "Giầy lội mưa") |
| Đoạn transcript đã làm sạch | 259 |
| Case Triệu chứng → Nguyên nhân → Cách sửa | 53 |
| Graph | 369 node, 469 cạnh |
| Nhóm kiến thức | nhiên liệu, động cơ, điện, khung sườn, truyền động, thân vỏ, dụng cụ hàn cắt |

## Chạy

```bash
python dxa.py build                 # dựng 4 tầng
python validate.py                  # kiểm tra bước 1-4
python eval.py                      # chấm điểm bước 5
python dxa.py ask "xe de lau bi chay xang"
python dxa.py sql "select * from specs"
```

## Kiểm thử ở từng bước

| Bước | Có thể hỏng thế nào | Cách kiểm (`validate.py`, `eval.py`) | Kết quả |
|---|---|---|---|
| 1. Lấy phụ đề | Thiếu video, phụ đề rỗng hoặc bị cắt | Số chữ/phút so với thời lượng; mốc giây cuối so với độ dài video | PASS |
| 2. Làm sạch | Còn lỗi nghe sai, mốc giây sai | Danh sách lỗi nghe sai phải về 0; mốc giây tăng dần, không vượt video; đoạn không quá ngắn/dài | PASS (đã bắt 1 lỗi "xú bắp" và sửa) |
| 3. Rút tri thức | **Bịa** con số hoặc nội dung | (a) Mọi con số trong thông số phải có trong phụ đề (hiểu 1 dem = 0.1 mm). (b) Cụm 2 chữ của triệu chứng + cách sửa phải có trong phụ đề ±3 phút quanh giây `t` | PASS (đã bắt 1 thông số suy diễn ở C52 và sửa) |
| 4. Graph + SQL | Thiếu liên kết, đếm lệch | Triệu chứng nào cũng có nguyên nhân và cách sửa; cạnh nào cũng có video nguồn; số dòng SQL khớp JSON | PASS |
| 5. Hỏi đáp | Trả lời sai bài, hoặc đoán bừa | 39 câu có đáp án + 8 câu ngoài phạm vi | Hit@1 38/39, Hit@3 39/39, từ chối đúng 8/8 |
| 6. Thợ duyệt | Hiểu sai nghề, máy không bắt được | Thợ đọc các case trên bảng duyệt | **Duyệt tạm** (17/11/2026): cả 53 case để "Đúng", ghi chú "Duyệt tạm, chưa xem kỹ". Chưa có thợ đọc thật |

**Đã thử bộ kiểm có bắt được bịa không:** cài một case giả ("hao xăng do bugi bạch kim", khe hở 0.9 mm). Bộ kiểm báo FAIL cả con số lẫn nội dung (độ phủ 0%). Case thật thấp nhất 18%.

## Kết quả cần đọc kỹ

- **Điểm 97–100% đang cao hơn thực tế.** Người dựng hệ thống tự viết câu hỏi, và các ngưỡng (`MIN_BM25`, `MIN_COVER`) được chỉnh trên chính bộ câu hỏi đó. Cần một **bộ câu hỏi riêng** lấy từ bình luận YouTube, chỉ dùng để chấm, không dùng để chỉnh.
- **Ngưỡng từ chối hỏng khi thêm dữ liệu.** Ở 10 video, chỉ cần BM25 là đủ. Lên 30 video thì chỉ còn từ chối đúng 4/8 ("lốp xe bị **xì**" khớp với bài dây hàn bị xì). Đã sửa bằng điều kiện thứ hai: chữ hiếm trong câu hỏi phải có trong case trả lời. Mỗi lần nạp thêm video phải chạy lại `eval.py`.
- **Câu gõ không dấu còn yếu** ở bản offline: "binh xang con buong ga ma ga khong ve" ra đúng case nhưng ở vị trí 2. Bản Gemini thêm dấu trước khi tìm, cần chấm lại bằng `eval_gemini.py`.

## Cần thợ xem kỹ (vẫn còn, dù đã duyệt tạm)

- C23: "chiều cao nâng cam 10.5 mm, trên 11 không được": chưa chắc là thông số gì.
- C25: đấu rơ le 4 chân, video vẽ trên giấy nên phụ đề thiếu.
- C26, C38: kiểm tra sườn và canh bánh, phần lớn chỉ thấy bằng hình.
- C52: khe hở khâu nồi Takegawa "1 đến 2", phụ đề nghe chưa rõ đơn vị.
- C51 (xe Satria, ECU): video bán xe, chỉ lấy phần kỹ thuật.

## Giới hạn

1. Bản Gemini mới kiểm trên dữ liệu giả và Gemini giả. Chưa gọi Gemini thật, Qdrant thật, FastAPI thật.
2. Khi không có `GEMINI_API_KEY`, hệ thống vẫn chạy bản offline cũ (TF-IDF + câu trả lời ghép khuôn).
3. Phần chỉ có hình bị mất.
4. Transcript thô không lưu trong gói (chỉ có bản đã làm sạch), nên bước 3 kiểm trên bản sạch. Lần sau nên lưu cả bản thô để kiểm chặt hơn.

## Thợ duyệt (bước 6)

Bảng duyệt: **DXA – Duyệt 53 case sửa xe** (Claude Sheets, https://claude.ai/artifact/Qpw8FXBUenR3Ppm1w4B7U3).
- Mỗi dòng là một case, có link ▶ nhảy đúng giây trong video. 6 case ưu tiên "1 Cao" nằm trên cùng, tiếp theo là các case có thông số.
- Thợ chọn ở cột **Kết quả duyệt**: Đúng / Cần sửa / Sai, rồi ghi lý do vào cột **Ghi chú của thợ**.
- Hiện tại: cả 53 case là "Đúng" với ghi chú "Duyệt tạm, chưa xem kỹ". Khi thợ xem thật, đổi ghi chú để phân biệt.
- Duyệt xong: tải bảng về dạng .xlsx, rồi chạy
  `python import_review.py duyet_case.xlsx && python dxa.py build && python validate.py && python eval.py`
- Đúng → `reviewed: true`. Cần sửa → giữ lại kèm `review_note`. Sai → `status: rejected`: case vẫn còn trong file để truy vết nhưng không vào kho.

## Bản Gemini + FastAPI (17/11/2026)

Cài đặt và cách chạy: xem [README](../README.md).

- **Embedding:** `gemini-embedding-001`, 768 chiều, lưu Qdrant local (`index/qdrant`). Có cache, build lại không tốn tiền.
- **LLM:** `gemini-3.6-flash`. Đổi bằng biến `DXA_LLM_MODEL`.
- **Câu không dấu:** Gemini thêm dấu, code kiểm lại là chỉ được thêm dấu, không được đổi chữ.
- **Chống bịa:** từ chối 2 lớp (`dxa.in_scope()`, rồi LLM trả `KHONG_DU_THONG_TIN`). Câu trả lời có con số không nằm trong video hoặc mã case lạ thì bị bỏ, trả bản ghép khuôn.
- **API:** `POST /ask`, `GET /cases/{id}`, `GET /health`, `GET /unanswered`. Câu bị từ chối được lưu vào `data/unanswered.jsonl`.
- **Sửa lỗi nạp state:** `state.pkl` lưu class dưới tên `__main__`, nên `rag.py` tự đổi về `dxa` khi nạp.

## Việc tiếp theo

1. Tải bảng duyệt về .xlsx và chạy `import_review.py` để đưa kết quả duyệt tạm vào kho.
2. Đặt `GEMINI_API_KEY`, chạy `build_gemini.py` và `eval_gemini.py --llm` trên 30 video thật. Nếu từ chối sai thì chỉnh ngưỡng trong `dxa.py`.
3. Lấy 30–50 câu hỏi thật từ bình luận YouTube làm bộ chấm riêng.
4. Cho người dùng thật xài qua API. Thợ xem `/unanswered` để trả lời và gợi ý quay video mới.
5. Khi có thời gian: thợ xem lại 6 case "1 Cao".
