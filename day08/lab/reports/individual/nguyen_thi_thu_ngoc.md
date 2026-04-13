# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Nguyễn Thị Thu Ngọc
**Vai trò trong nhóm:** Documentation Owner
**Ngày nộp:** 2026-04-13
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Với vai trò Documentation Owner, tôi chịu trách nhiệm chính ở Sprint 4 — viết và hoàn thiện toàn bộ tài liệu kỹ thuật của nhóm.

Tôi thực hiện 3 commit chính vào `docs/`:

**Commit `edba4d2`**: Viết nội dung đầy đủ cho `docs/architecture.md` và `docs/tuning-log.md` — mô tả chunking decision, retrieval config, scorecard comparison. Đồng thời cập nhật `results/scorecard_baseline.md`, `scorecard_variant.md`, và `ab_comparison.csv` để phản ánh đúng dữ liệu từ pipeline đã chạy.

**Commit `00b389d`**: Thêm 2 sơ đồ Mermaid chi tiết vào `architecture.md` — một cho indexing pipeline (từ `python index.py` đến ChromaDB), một cho retrieval+generation pipeline (từ `rag_answer()` đến output). Mermaid cho phép sơ đồ render trực tiếp trên GitHub.

**Commit `6bed63d`**: Sửa lỗi nhỏ trong `architecture.md`.

Ngoài ra, tôi đảm nhận vai trò merge PR #3 (Document branch) vào main, kiểm tra không có conflict với các phần code của Khang và Duy.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Điều tôi hiểu rõ nhất sau lab là **tại sao pipeline diagram quan trọng hơn code comment**.

Trước lab, tôi nghĩ viết documentation chỉ là dịch lại những gì code đã làm. Khi thực sự vẽ Mermaid chart cho indexing pipeline, tôi phát hiện ra flow thực tế phức tạp hơn tưởng: `get_embedding()` có 2 nhánh (OpenAI vs local SentenceTransformer, chọn qua env var), `_split_by_size()` có 3 tầng split (section → paragraph → character), và ChromaDB `upsert` cần metadata được ép sang `str` vì ChromaDB không nhận kiểu `None`.

Việc vẽ diagram buộc tôi phải đọc kỹ `index.py` line by line. Tôi tìm thấy chi tiết này trong commit của Thuc (7b98138) mà nếu chỉ đọc commit message "Refactor document preprocessing" sẽ bỏ sót. **Documentation không phải là output cuối — nó là công cụ hiểu code.**

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Khó nhất là **đồng bộ số liệu giữa scorecard files và architecture doc**.

Khi tôi viết `architecture.md` lần đầu (commit `edba4d2`), tôi dùng số liệu từ scorecard của Duy đã generate. Nhưng sau đó Khang chạy lại eval với config mới (hybrid+rerank+expansion thay vì hybrid_only), các con số thay đổi. Tôi phải cập nhật cả `architecture.md` lẫn `tuning-log.md` để đồng bộ.

Điều này làm tôi nhận ra một vấn đề cấu trúc: **scorecard numbers trong doc nên đọc từ file, không hardcode**. Nếu ai đó chạy lại eval, doc sẽ lỗi thời ngay lập tức. Giải pháp lý tưởng là app.py đã làm — `_parse_scorecard_md()` đọc file trực tiếp. Documentation file thì không tự động update được, nhưng ít nhất có thể ghi rõ "Generated: timestamp" và link sang `results/scorecard_*.md` là nguồn chính.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi được chọn:** q06 — "Escalation trong sự cố P1 diễn ra như thế nào?"

**Phân tích:**

Cả baseline và variant đều cho Faithfulness=4, Relevance=5, Context Recall=5, Completeness=4 — gần perfect nhưng chưa đạt 5/5 ở Faithfulness và Completeness.

**Lỗi Faithfulness (4 thay vì 5):** Pipeline thêm chi tiết "engineer cập nhật tiến độ lên ticket mỗi 30 phút" — thông tin này có trong context (sla_p1_2026.txt đề cập update interval) nhưng LLM judge coi là "minor uncertain detail" vì chunk không ghi rõ số 30 phút. Đây là **borderline grounding issue** — thông tin thực ra có trong doc nhưng paraphrase gây ra uncertainty với judge.

**Lỗi Completeness (4 thay vì 5):** Expected answer tập trung vào "tự động escalate sau 10 phút không có response". Pipeline trả lời đúng nhưng gộp nhiều bước vào một paragraph dài, khiến judge cho rằng "key point về auto-escalation không được nhấn mạnh đủ."

**Lỗi nằm ở generation layer**, không phải retrieval: Context Recall = 5 xác nhận đúng source đã được retrieve. Cần prompt thêm: "List escalation steps as numbered bullet points" — sẽ giúp judge nhận rõ từng bước, cải thiện Completeness lên 5/5.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

1. **Automation cho documentation**: Viết script đọc `ab_comparison.csv` để tự động generate bảng so sánh trong `tuning-log.md`. Lần này tôi copy-paste thủ công — dễ sai khi eval chạy lại. 20 rows CSV chỉ cần Python 15 dòng để render thành bảng đúng.

2. **Thêm "failure mode gallery"** vào `architecture.md`: 3–4 ví dụ cụ thể (câu hỏi, retrieved chunks, answer, diagnosis) trực tiếp từ `ab_comparison.csv` — có giá trị cao hơn mô tả trừu tượng.

---

*File: `reports/individual/nguyen_thi_thu_ngoc.md`*
