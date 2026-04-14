# Routing Decisions Log — Lab Day 09

**Nhóm:** Nhom25  
**Ngày:** 14/04/2026

> Tài liệu này bám theo luồng trong sơ đồ supervisor-worker:
> Supervisor quyết định route giữa `retrieval_worker`, `policy_tool_worker`, hoặc `human_review`; sau đó luôn đi qua `synthesis_worker` để tạo output cuối.

---

## Routing Decision #1

**Trace:** `run_20260414_165234_789684.json`  
**Task đầu vào:**
> Nhân viên được làm remote tối đa mấy ngày mỗi tuần?

**Worker được chọn:** `retrieval_worker`  
**Route reason (từ trace):** `matches knowledge keywords: ['remote']`  
**MCP tools được gọi:** Không có  
**Workers called sequence:** `retrieval_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Nhân viên sau probation được remote tối đa 2 ngày/tuần, cần Team Lead phê duyệt.
- confidence: `0.79`
- Correct routing? `Yes`

**Nhận xét:** Routing đúng vì đây là câu hỏi kiến thức nội bộ HR, không cần policy exception engine và không cần gọi MCP tool.

---

## Routing Decision #2

**Trace:** `run_20260414_165241_316017.json`  
**Task đầu vào:**
> Sản phẩm kỹ thuật số (license key) có được hoàn tiền không?

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `matches policy/access keywords: ['hoàn tiền', 'license', 'kỹ thuật số']`  
**MCP tools được gọi:** Không có  
**Workers called sequence:** `retrieval_worker -> policy_tool_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Không được hoàn tiền do thuộc ngoại lệ sản phẩm kỹ thuật số theo policy refund.
- confidence: `0.64`
- Correct routing? `Yes`

**Nhận xét:** Routing đúng vì câu hỏi yêu cầu áp dụng rule/exception của policy, không chỉ truy xuất fact đơn thuần.

---

## Routing Decision #3

**Trace:** `run_20260414_165302_628279.json`  
**Task đầu vào:**
> Ticket P1 lúc 2am, cần cấp Level 2 access tạm thời cho contractor để emergency fix và đồng thời notify stakeholders theo SLA.

**Worker được chọn:** `policy_tool_worker`  
**Route reason (từ trace):** `matches policy/access keywords: ['level 2', 'contractor'] | risk signals: ['emergency', '2am'] | access question → will call MCP check_access_permission | multi-hop SLA+access → policy_tool_worker with MCP`  
**MCP tools được gọi:** `check_access_permission`, `get_ticket_info`  
**Workers called sequence:** `retrieval_worker -> policy_tool_worker -> synthesis_worker`

**Kết quả thực tế:**
- final_answer (ngắn): Trả lời đầy đủ 2 nhánh: điều kiện cấp quyền tạm thời (24h, cần phê duyệt/ghi log) và quy trình notify theo SLA P1.
- confidence: `0.82`
- Correct routing? `Yes`

**Nhận xét:** Đây là routing đa bước đúng theo sơ đồ: cần retrieval evidence + policy check + MCP để hợp nhất SLA và access control.

---

## Routing Decision #4 (tuỳ chọn — bonus)

**Trace:** `run_20260414_165247_961959.json`  
**Task đầu vào:**
> ERR-403-AUTH là lỗi gì và cách xử lý?

**Worker được chọn:** `human_review` (sau đó auto-approve fallback về `retrieval_worker` trong lab mode)  
**Route reason:** `no specific keyword → default retrieval_worker | risk signals: ['err-'] | unknown error code detected → human_review | human_review auto-approved → retrieval`

**Kết quả thực tế:**
- final_answer (ngắn): Không đủ thông tin trong tài liệu nội bộ.
- confidence: `0.44`
- Correct routing? `Yes (safe fallback)`

**Nhận xét: Đây là trường hợp routing khó nhất trong lab. Tại sao?**

Không có tri thức trực tiếp về mã lỗi cụ thể trong KB; hệ thống ưu tiên an toàn bằng HITL trigger trước khi trả lời. Trường hợp này cho thấy giá trị của nhánh `human_review` trong các query mơ hồ/rủi ro.

---

## Tổng kết

### Routing Distribution

| Worker | Số câu được route | % tổng |
|--------|------------------|--------|
| retrieval_worker | 8 | 53.3% |
| policy_tool_worker | 7 | 46.7% |
| human_review | 0* | 0.0% |

\* Theo thống kê route cuối cùng trong eval; có `1/15` case trigger HITL rồi auto-approve về retrieval.

### Routing Accuracy

> Trong số 15 câu đã chạy eval, supervisor route đúng bao nhiêu?

- Câu route đúng: `14 / 15` (`93.33%`)
- Câu route sai (đã sửa bằng cách nào?): `1` câu (`q02`) bị route sang `policy_tool_worker` thay vì `retrieval_worker`; hướng cải tiến là tinh chỉnh keyword `hoàn tiền` theo intent (fact retrieval vs policy adjudication).
- Câu trigger HITL: `1 / 15`

### Lesson Learned về Routing

1. Keyword routing đủ nhanh và dễ debug cho lab, nhưng cần thêm tầng phân loại intent để giảm false positive ở nhóm câu hỏi fact đơn giản có chứa từ policy.
2. Multi-hop query (SLA + Access) nên ưu tiên `policy_tool_worker` với MCP vì cần hợp nhất nhiều nguồn và luật phê duyệt.

### Route Reason Quality

`route_reason` hiện tại đã hữu ích để debug vì có thể hiện keyword hit, risk signal, override và lý do gọi MCP. Tuy nhiên nên chuẩn hoá thành format có cấu trúc (vd. `decision_path`, `matched_keywords`, `overrides`, `tool_plan`) để dễ thống kê và đánh giá tự động.
