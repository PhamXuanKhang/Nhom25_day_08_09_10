# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Nguyễn Văn Thức
**Vai trò trong nhóm:** Retrieval Owner
**Ngày nộp:** 2026-04-13
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Với vai trò Retrieval Owner, tôi chịu trách nhiệm chính ở Sprint 1 — toàn bộ indexing pipeline trong `index.py`.

**Commit `7b98138`** (128 insertions, 61 deletions — thay đổi lớn nhất ở Sprint 1): Tôi refactor toàn bộ `preprocess_document()` và `_split_by_size()` từ template TODO sang implementation thực.

Cụ thể tôi implement:
- `preprocess_document()`: Thay thế `startswith("Source:")` bằng regex `r"^(Source|Department|Effective Date|Access):\s*(.+)$"` — xử lý đúng edge case như trailing space và mixed-case header.
- Text normalization: 3 lớp regex (`\r\n?`, `[ \t]+\n`, `\n{3,}`) để chuẩn hóa whitespace trước khi chunk.
- `_split_by_size()`: Implement paragraph-based chunking với priority queue — split theo `\n\n` trước, nếu paragraph quá dài mới fallback sang `\n`, rồi `. ` — luôn cắt tại ranh giới tự nhiên thay vì giữa câu.
- Overlap: Lấy đoạn cuối chunk trước (trim đến newline gần nhất) ghép đầu chunk tiếp theo để preserve context.
- Dual embedding: `get_embedding()` check `EMBEDDING_PROVIDER` env var, route sang OpenAI `text-embedding-3-small` hoặc local `SentenceTransformer`.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Điều tôi hiểu rõ nhất là **chunking strategy ảnh hưởng đến toàn bộ pipeline downstream, không chỉ indexing**.

Trước lab, tôi nghĩ chunking chỉ là "cắt text thành đoạn nhỏ". Sau khi implement và thấy kết quả eval, tôi hiểu: nếu một điều khoản chính sách bị cắt giữa câu điều kiện và câu hệ quả, LLM sẽ chỉ nhìn thấy một nửa và generate answer sai — dù retrieval đã lấy đúng document. Đây là lý do tại sao `_split_by_size()` phải implement priority-based boundary detection (paragraph > line break > sentence end) thay vì cắt cứng theo character count.

Kết quả thực tế xác nhận: Context Recall đạt 5.00/5 trên cả hai config — tức là không có expected source nào bị bỏ sót. Đây là thước đo trực tiếp chất lượng indexing. Chunk tốt → retrieval có gì để tìm → recall cao.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Khó khăn lớn nhất là **implement overlap đúng cách mà không tạo ra duplicate content**.

Giả thuyết ban đầu: chỉ cần lấy 80 chars cuối của chunk trước ghép vào đầu chunk tiếp theo. Thực tế: nếu overlap bắt đầu giữa một từ, chunk tiếp theo sẽ có "nửa câu" ở đầu, gây ra hallucination khi LLM đọc.

Tôi fix bằng cách tìm newline gần nhất trong vùng overlap:
```python
tail = prev[-overlap_chars:]
nl = tail.find("\n")
if 0 < nl < len(tail) - 10:
    tail = tail[nl + 1:].lstrip()
```
Điều này đảm bảo overlap luôn bắt đầu từ đầu một câu hoàn chỉnh.

Điều ngạc nhiên: ChromaDB `upsert` yêu cầu metadata fields phải là `str`, không nhận `None`. Tôi phải thêm `{k: str(v) if v is not None else "" for k, v in chunk["metadata"].items()}` trong `build_index()`. Nếu không có bước này, toàn bộ index build sẽ crash ở file đầu tiên.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi được chọn:** q03 — "Ai phải phê duyệt để cấp quyền Level 3?"

**Phân tích:**

**Baseline** (Faithfulness=4, Relevance=5, Recall=5, Completeness=5): Pipeline trả lời gần đúng — "cần phê duyệt của Line Manager, IT Admin và IT Security" — nhưng judge cho Faithfulness=4 vì answer không explicitly cite IT Security approval từ text gốc.

**Variant** (Faithfulness=2, Relevance=5, Recall=5, Completeness=5): Cùng câu trả lời về nội dung nhưng Faithfulness giảm mạnh xuống 2/5. Đây là regression nghiêm trọng nhất của hybrid config.

**Nguyên nhân tôi trace được từ phía indexing**: `access_control_sop.txt` có nhiều section nói về approval — Section "Level 1", "Level 2", "Level 3", và "Temporary Access". BM25 trong hybrid retrieve chunk "Temporary Access" cao vì nó có từ "approval" lặp đi lặp lại nhiều lần hơn chunk "Level 3". LLM reranker sau đó bị confuse vì cả hai chunk đều liên quan đến access control.

**Lỗi nằm ở intersection của indexing và retrieval**: Chunking đã chunk đúng theo section (mỗi access level là một chunk), nhưng BM25 score lại không phân biệt được section-level semantics. Nếu tôi thêm `section` vào BM25 tokenized corpus (không chỉ body text), keyword matching sẽ chính xác hơn.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

1. **Thêm metadata chunk per document**: Mỗi tài liệu có một chunk mở đầu ghi rõ tên hiện tại và tên cũ (ví dụ: "Access Control SOP, trước đây: Approval Matrix for System Access"). Không cần thay đổi retrieval, chỉ thêm vào `build_index()`. Sẽ fix q07 vĩnh viễn.

2. **Include section name trong BM25**: Nối `section + " " + text` khi tokenize. Giảm keyword collision giữa các section trong cùng file — đặc biệt `access_control_sop.txt` có nhiều section approval gần giống nhau.

---

*File: `reports/individual/nguyen_van_thuc.md`*
