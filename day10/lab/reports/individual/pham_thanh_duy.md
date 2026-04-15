# Báo cáo cá nhân

**Họ và tên:** Phạm Thành Duy
**Vai trò:** Cleaning & Quality Owner (Sprint 1-3)
**Độ dài:** ~450 từ

---

## 1. Phụ trách cụ thể
Trong lab này, tôi đảm nhận vai trò **Cleaning & Quality Owner** (Sprint 1-3). Công việc chính của tôi bao gồm:
- Triển khai và mở rộng file `transform/cleaning_rules.py`: Xây dựng các rule để lọc ký tự tàng hình (BOM, zero-width) (Rule 7), quarantine các bản ghi có `effective_date` ở tương lai xa (Rule 8), phát hiện chunk text có độ dài bất thường (Rule 9) và normalize marker version `policy-v3` thành `policy-v4` (Rule 10).
- Triển khai `quality/expectations.py`: Thêm các rule kiểm định chất lượng (Expectations) trước khi nhúng (embed) vào ChromaDB. Cụ thể là E7 (đảm bảo tính duy nhất của `chunk_id`), E8 (cảnh báo nếu thiếu `doc_id` quan trọng) và E9 (đảm bảo không còn ký tự tàng hình nào lọt qua khâu clean).
- Kết nối chặt chẽ với quy trình ETL `etl_pipeline.py` để đảm bảo những rule này sẽ sinh ra số liệu quarantine/cleaned chính xác ghi vào manifest.

**Bằng chứng:** Thông tin `raw=10 clean=6 quar=4` trong file `manifest_sprint-final.json`.

---

## 2. Quyết định kỹ thuật
**Warn vs Halt (trong Expectation):** 
Đối với việc kiểm tra tính duy nhất của `chunk_id` (E7), tôi đặt severity là **halt** vì nếu để `chunk_id` trùng lặp, việc upsert dữ liệu vào vector database sẽ gây ra xung đột hoặc mất mát dữ liệu quan trọng một cách âm thầm. Ngược lại, đối với Expectation E8 (kiểm tra có đủ các `doc_id` thiết yếu hay không), tôi thiết lập severity là **warn**. Lý do là việc thiếu một phần tài liệu không gây ảnh hưởng làm hỏng collection hiện tại của người dùng, mà chỉ làm giảm độ đầy đủ của hệ thống RAG, hệ thống vẫn có thể chạy và cần ghi log để đội Ingestion khắc phục sau.

**Bảo vệ độ ổn định của Tokenizer (R7 & E9):**
Quyết định loại bỏ các ký tự tàng hình (Zero-width space, BOM) ngay từ sớm (`_strip_invisible` trong cleaning layer) và validate lại ở lớp expectation (E9) nhằm giúp hàm hash deduplication hoạt động chính xác và tokenizer của embedding model không sinh ra các token rác, nâng cao chất lượng tìm kiếm semantic.

---

## 3. Sự cố / Anomaly phát hiện được
**Phát hiện Anomaly:** Trong quá trình clean, hệ thống sinh ra một lượng quarantine đáng kể. Khi điều tra file CSV nguyên bản, tôi phát hiện một số chunk của policy bị lỗi export có `effective_date` hoặc chuỗi bị đính kèm các khoảng trắng tàng hình (`\ufeff`) và các đoạn text dính liền do format sai từ nguồn.
**Khắc phục:** Viết riêng rule R7 để lọc bỏ danh sách các `_INVISIBLE_CHARS` khi đọc text và rule R8 để quarantine các chunk có ngày tương lai xa bất hợp lý (> 2 năm). Việc này đã chuyển thành công các bản ghi hỏng/không hợp lý sang tập quarantine thay vì làm giảm chất lượng RAG. 

---

## 4. Before / After Evidence
Trước khi đưa vào luật dọn dẹp và expectation, quá trình embed diễn ra cả với các dữ liệu stale ("14 ngày làm việc" và "10 ngày phép năm"). Quá trình retrieval trả về sai chính sách.
Sau khi can thiệp ở lớp Transformation & Quality:
- **Log ETL chuẩn:** `OK manifest run_id=sprint-final raw=10 clean=6 quar=4`
- **Eval Grading:** Kết quả JSONL cho đánh giá `gq_d10_01` và `gq_d10_03` đạt **OK** (Sạch bóng từ khóa "14 ngày làm việc" / "10 ngày phép năm" trong toàn bộ `top-k` được truy xuất), chứng minh pipeline xử lý quality đã gắp thành công chunk đúng phiên bản.

---

## 5. Cải tiến thêm (Hướng 2 giờ tiếp theo)
**Tích hợp Great Expectations hoặc Pydantic:** Hiện tại `run_expectations` đang sử dụng logic thuần Python để validate. Để mở rộng và duy trì (maintain) lâu dài trong Product thực tế, tôi sẽ bỏ ra 2 giờ tiếp theo cấu trúc lại các expectaton E1-E9 dưới dạng model Pydantic schemas (như `CleanedRow` model) để có thể auto-validate type/length/format với hiệu năng cao hơn và mã nguồn gọn gàng hơn.