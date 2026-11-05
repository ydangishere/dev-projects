"""The full 15-row human-review checklist; never automatically modify code or tickets."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Scenario:
    id: int
    situation: str
    problem: str
    fix: str
    tools: str
    pattern: str
    priority: str

SCENARIOS = [
    Scenario(1, "Bệnh nhân mở lịch khám nhưng màn hình báo lỗi 500.", "API bị lỗi, không trả được dữ liệu", "Xem nhật ký lỗi, tìm đoạn code hoặc truy vấn bị lỗi và sửa nguyên nhân.", "Postman, Node.js Logs", r"\b500\b|internal server|api (?:error|failure)|lỗi máy chủ", "P1"),
    Scenario(2, "Hai bệnh nhân cùng đặt bác sĩ lúc 9 giờ và cả hai đều thành công.", "Hai bệnh nhân đặt trùng giờ khám", "Tái hiện yêu cầu đồng thời; thêm ràng buộc không trùng lịch còn hiệu lực, xử lý lỗi 409.", "PostgreSQL UNIQUE, Transaction", r"double.book|same (?:appointment )?slot|duplicate appointment|trùng (?:giờ|lịch)|race condition", "P1"),
    Scenario(3, "Bệnh nhân bấm thanh toán 3 lần vì mạng chậm và bị trừ tiền nhiều lần.", "Bị trừ tiền nhiều lần", "Đối soát trước; dùng mã yêu cầu duy nhất và lưu kết quả để không xử lý thanh toán lặp.", "Idempotency-Key, PostgreSQL", r"charg(?:ed|ing) twice|double.charg|duplicate payment|trừ tiền.*(?:lần|nhiều)|payment.*(?:twice|duplicate)", "P0"),
    Scenario(4, "Danh sách 1.000 lịch khám tải mất 10 giây.", "Hệ thống phản hồi quá chậm", "Tìm truy vấn chậm, kiểm tra chỉ mục và phân trang.", "PostgreSQL EXPLAIN ANALYZE", r"latency|slow (?:api|query|page)|takes? 10 seconds|10s|phản hồi.*chậm|tải.*giây", "P2"),
    Scenario(5, "Bệnh nhân A sửa mã hồ sơ trên đường dẫn rồi xem được hồ sơ của B.", "Bệnh nhân xem được hồ sơ người khác", "Chặn truy cập trái phép tại backend; kiểm tra quyền hồ sơ, bổ sung kiểm thử bảo mật.", "Authorization, JWT, Supabase RLS", r"another patient|other patient.*record|unauthori[sz]ed.*record|access.*medical record|hồ sơ.*người khác|idor", "P0"),
    Scenario(6, "Bác sĩ đã đăng nhập nhưng liên tục bị yêu cầu đăng nhập lại.", "Người dùng không duy trì được đăng nhập", "Kiểm tra thời hạn token, cách làm mới phiên và cấu hình xác thực.", "Supabase Auth, JWT, Logs", r"login|log.in|session expir|session invalid|đăng nhập|phiên.*hết hạn", "P2"),
    Scenario(7, "Thêm cột bắt buộc vào bảng lớn, dữ liệu cũ chưa có giá trị.", "Cập nhật database làm ứng dụng bị lỗi", "Triển khai theo bước: cột cho phép trống, điền dữ liệu cũ, rồi mới ràng buộc bắt buộc.", "PostgreSQL, SQL Migration", r"migration|schema change|required column|not null|thêm cột|cột bắt buộc", "P1"),
    Scenario(8, "Bác sĩ gửi đơn thuốc nhưng hệ thống nhà thuốc ngừng phản hồi.", "Không kết nối được nhà thuốc", "Giới hạn thời gian chờ, lưu yêu cầu và thử lại có kiểm soát.", "Node.js, Queue, Logs", r"pharmacy.*(?:timeout|unavailable|down)|nhà thuốc.*(?:không phản hồi|mất kết nối)|prescription.*timeout", "P1"),
    Scenario(9, "Ngân hàng báo đã thu tiền nhưng ứng dụng vẫn báo chờ tạo đơn.", "Thanh toán thành công nhưng đơn hàng chưa được tạo", "Kiểm tra webhook, đối soát trạng thái và tiếp tục tạo đơn, không thu tiền lần nữa.", "Webhook, PostgreSQL, Queue", r"paid.*(?:no order|missing order)|payment success.*(?:order|prescription)|thanh toán.*(?:đơn thuốc|đơn hàng)|webhook.*order", "P1"),
    Scenario(10, "Bác sĩ đổi giờ khám nhưng bệnh nhân vẫn thấy giờ cũ.", "Giao diện hiển thị thông tin cũ", "Kiểm tra cache và cập nhật dữ liệu giao diện sau thao tác lưu.", "React DevTools, Next.js", r"stale (?:data|cache)|old (?:appointment )?time|outdated (?:screen|data)|thông tin cũ|giờ cũ", "P2"),
    Scenario(11, "Yêu cầu sửa một nút nhưng AI thay đổi 15 file.", "AI sửa sai code hoặc sửa quá nhiều file", "Dùng Git diff so sánh trước và sau, bỏ sửa đổi ngoài phạm vi, chạy kiểm thử.", "git diff, Jest", r"ai.*(?:15 files|many files|unrelated files)|ai sửa|agent.*changed.*files|generated code.*regression", "P2"),
    Scenario(12, "Đặt lịch thành công trên máy lập trình nhưng lên server báo lỗi.", "Ứng dụng chạy local nhưng lỗi production", "So sánh cấu hình, biến môi trường, phiên bản và kết nối database.", "Docker, CI/CD, Logs", r"works? (?:on )?local|local.*production|local.*server|chạy local|chạy trên máy.*server", "P1"),
    Scenario(13, "Sửa đặt lịch xong thì chức năng hủy lịch không chạy.", "Sửa một lỗi nhưng làm hỏng chức năng khác", "Viết kiểm thử tái hiện lỗi, chạy lại các luồng liên quan trước khi triển khai.", "Jest, Playwright", r"regression|fix.*broke|after fix.*fail|sửa.*hỏng|cancel.*after.*fix", "P1"),
    Scenario(14, "Hai nhân viên cùng sửa số điện thoại, dữ liệu người trước bị ghi đè.", "Hai người cùng sửa hồ sơ gây mất dữ liệu", "Kiểm tra phiên bản hồ sơ trước khi lưu, báo xung đột thay vì ghi đè.", "PostgreSQL, Version Column", r"lost update|two editors|two users.*update|overwrite.*changes|cùng (?:sửa|cập nhật)|ghi đè", "P1"),
    Scenario(15, "Sau triển khai phiên bản mới, nhiều bệnh nhân không mở được lịch khám.", "Cập nhật ứng dụng xong phát sinh lỗi", "Kiểm tra cảnh báo và log, quay lại bản ổn định khi cần, xác nhận hồi phục.", "Git, CI/CD, Monitoring", r"after deploy|after release|post.deployment|sau triển khai|deploy.*fail|deployment.*outage", "P1"),
]
BY_ID = {s.id: s for s in SCENARIOS}
