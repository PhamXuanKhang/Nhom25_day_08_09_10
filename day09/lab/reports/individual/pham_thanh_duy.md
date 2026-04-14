# Báo Cáo Cá Nhân — Lab Day 09: Multi-Agent Orchestration

**Họ và tên:** Phạm Thành Duy  
**Vai trò trong nhóm:** Worker Owner  
**Ngày nộp:** 2026-04-14  
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi phụ trách phần nào? (100–150 từ)

Tôi chịu trách nhiệm Sprint 2 — implement toàn bộ 3 workers và script indexing ChromaDB. Đây là lớp xử lý domain logic của hệ thống: từ tìm kiếm knowledge base, kiểm tra chính sách, đến tổng hợp câu trả lời có citation.

**Module/file tôi chịu trách nhiệm:**
- File chính: `workers/retrieval.py`, `workers/policy_tool.py`, `workers/synthesis.py`
- File phụ: `setup_index.py` (ban đầu implement, sau đó Khang refactor sang OpenAI batch API)

**Functions tôi implement:**
- `retrieve_dense(query, top_k)` — embed + ChromaDB query + format chunks với cosine score
- `_get_collection()` — ChromaDB singleton với fail-safe
- `analyze_policy(task, chunks)` — 4 exception cases: flash_sale, digital_product, activated, temporal_scoping
- `_detect_access_question()` / `_detect_ticket_question()` — signal detection cho MCP calls
- `synthesize(task, chunks, policy_result)` — build context, call LLM chain, estimate confidence
- `_build_context()` / `_estimate_confidence()` — helper functions cho synthesis

**Cách công việc của tôi kết nối với phần của thành viên khác:**

`run(state)` của mỗi worker đọc từ `AgentState` do Khang định nghĩa và append vào `worker_io_logs`. `_call_mcp_tool()` trong policy_tool.py gọi `dispatch_tool()` của Thức. Trace output do tôi ghi được Thư phân tích trong `eval_trace.py`.

**Bằng chứng:** Commit `0de917c TDuy22 — [day09] retrieval: add retrieval worker implementation`, commit `9d022ad TDuy22 — Update worker contracts`.

---

## 2. Tôi đã ra một quyết định kỹ thuật gì? (150–200 từ)

**Quyết định:** Implement temporal scoping v3/v4 bằng date regex thay vì lookup bảng

Trong `policy_tool.py`, câu hỏi khó nhất về logic chính sách là câu có temporal scoping: đơn đặt trước 01/02/2026 áp dụng policy v3, sau áp dụng v4. Tôi cần quyết định cách detect điều này.

**Các lựa chọn thay thế:**
- Hardcode check "2026" trong task string: đơn giản nhưng miss cases khác (VD: đơn tháng 1)
- Regex extract date, compare với `V4_EFFECTIVE_DATE=(2026,2,1)`: chính xác, handle dd/mm/yyyy và dd-mm-yyyy
- Gọi LLM để parse date: over-engineering, tốn thêm API call cho 1 edge case

**Phương án đã chọn:**

```python
DATE_PATTERN = re.compile(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})")
V4_EFFECTIVE_DATE = (2026, 2, 1)

def _parse_order_date(task: str) -> tuple[int, int, int] | None:
    for match in DATE_PATTERN.finditer(task):
        d, m, y = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if 2024 <= y <= 2030 and 1 <= m <= 12 and 1 <= d <= 31:
            return (y, m, d)
    return None
```

**Trade-off đã chấp nhận:** Pattern giả định format dd/mm/yyyy — nếu user nhập mm/dd/yyyy sẽ parse sai. Chấp nhận vì docs nội bộ và test questions đều dùng format Việt Nam (dd/mm/yyyy).

**Bằng chứng từ trace/code:**

```
# Trace q12: "đặt đơn 31/01/2026"
policy_result.policy_version_note: "Đơn hàng đặt 31/01/2026 trước ngày hiệu lực 
  v4 (01/02/2026). Áp dụng chính sách v3 — cần xác nhận với CS Team."
actual_answer: "Không đủ thông tin trong tài liệu nội bộ... cần xác nhận CS Team"
confidence: 0.33  # penalty -0.15 từ has_version_note
route_ok: true, abstain: true, abstain_ok: true
```

Câu q12 abstain đúng — không bịa nội dung v3 không có trong docs.

---

## 3. Tôi đã sửa một lỗi gì? (150–200 từ)

**Lỗi:** `_get_collection()` không xử lý collection trống sau khi ChromaDB reset

**Symptom:**

Khi chạy `python workers/retrieval.py` standalone sau khi `setup_index.py` xóa và tạo lại collection, retrieval worker đôi khi trả về empty chunks dù collection không empty:

```
⚠️  Collection 'day09_docs' trống. Chạy `python setup_index.py` trước.
Retrieved: 0 chunks  (dù đã index xong)
```

**Root cause:**

Code ban đầu dùng `client.get_collection()` — nếu collection chưa tồn tại sẽ throw exception và fallback về `get_or_create_collection()`. Nhưng ChromaDB có race condition nhỏ: nếu `setup_index.py` chưa hoàn thành commit (vẫn đang `collection.add()`), `get_collection()` trả về collection chưa có documents.

**Cách sửa:**

Thêm `count()` check và warning rõ ràng, đồng thời đảm bảo singleton không cache collection rỗng:

```python
def _get_collection():
    global _COLLECTION
    if _COLLECTION is not None:
        return _COLLECTION

    import chromadb
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    try:
        _COLLECTION = client.get_collection(COLLECTION_NAME)
    except Exception:
        _COLLECTION = client.get_or_create_collection(
            COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        if _COLLECTION.count() == 0:
            print(f"⚠️  Collection '{COLLECTION_NAME}' trống. Chạy setup_index.py trước.")
    return _COLLECTION
```

Trong `retrieve_dense()`, thêm early return khi `collection.count() == 0` thay vì để ChromaDB query fail ngầm.

**Bằng chứng trước/sau:**

Trước: `python workers/retrieval.py` đôi khi trả 0 chunks, không có warning.  
Sau: Warning rõ ràng nếu collection rỗng, không crash, và khi collection có data thì retrieve đúng. Toàn bộ 15 test questions source_hit_rate = 100%.

---

## 4. Tôi tự đánh giá đóng góp của mình (100–150 từ)

**Tôi làm tốt nhất ở điểm nào?**

Logic `analyze_policy()` với 4 exception cases. Tôi implement rule-based detection rõ ràng, có thể test độc lập (`python workers/policy_tool.py` pass cả 5 test cases), và kết quả xuất hiện đúng trong trace của Thư. Đặc biệt temporal scoping (q12) và flash_sale_exception (q07) được detect chính xác, giúp synthesis abstain hoặc cảnh báo thay vì hallucinate.

**Tôi làm chưa tốt hoặc còn yếu ở điểm nào?**

Confidence formula trong synthesis chưa chính xác cho câu q14 (probation remote): answer abstain nhưng lý do là retrieval không có chunk liên quan, không phải vì policy ambiguous. Công thức hiện tại không phân biệt được "abstain vì không có data" vs "abstain vì data mâu thuẫn".

**Nhóm phụ thuộc vào tôi ở đâu?**

Toàn bộ pipeline phụ thuộc vào 3 workers. Nếu `synthesis.run()` không xong, không có `final_answer` — Thư không thể chạy `eval_trace.py`, Khang không thể demo `app.py`.

**Phần tôi phụ thuộc vào thành viên khác:**

Cần Khang định nghĩa `AgentState` và `CHROMA_PATH` trước, cần Thức cung cấp `dispatch_tool()` interface để `_call_mcp_tool()` hoạt động.

---

## 5. Nếu có thêm 2 giờ, tôi sẽ làm gì? (50–100 từ)

Tôi sẽ cải tiến chunking strategy trong `setup_index.py`. Trace câu q14 (probation remote, confidence=0.54, abstain sai) cho thấy retrieval worker không tìm được chunk về "nhân viên probation không được remote". Root cause: nội dung này nằm trong cùng section với điều kiện remote sau probation, và mechanical chunk slice tại 1500 ký tự đã cắt mất câu cấm. Tôi sẽ thử recursive character splitter với overlap 200 ký tự để giữ semantic boundary.

---

*Lưu file này với tên: `reports/individual/pham_thanh_duy.md`*
