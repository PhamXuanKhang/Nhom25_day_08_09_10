# Architecture — RAG Pipeline (Day 08 Lab)

> Template: Điền vào các mục này khi hoàn thành từng sprint.
> Deliverable của Documentation Owner.

## 1. Tổng quan kiến trúc

```
[Raw Docs]
    ↓
[index.py: Preprocess → Chunk → Embed → Store]
    ↓
[ChromaDB Vector Store]
    ↓
[rag_answer.py: Query → Retrieve → Rerank → Generate]
    ↓
[Grounded Answer + Citation]
```

**Mô tả ngắn gọn:**
> Hệ thống RAG trả lời câu hỏi về chính sách công ty (SLA, hoàn tiền, access control, HR, IT helpdesk). 
> Dùng vector search để tìm document chunks liên quan, rồi dùng LLM sinh câu trả lời có trích dẫn nguồn. 
> Giải quyết vấn đề: tìm kiếm policy thủ công chậm → tự động hóa bằng RAG, độ chính xác 4.58/5.

---

## 2. Indexing Pipeline (Sprint 1)

### Tài liệu được index
| File | Department | Content | Chunks |
|------|-----------|---------|--------|
| `policy_refund_v4.txt` | Customer Service | Refund policies, timelines, exceptions | 6 |
| `sla_p1_2026.txt` | IT Support | SLA targets, escalation procedures, P1 handling | 5 |
| `access_control_sop.txt` | IT Security | Access levels, approval matrix, temporary access | 7 |
| `it_helpdesk_faq.txt` | IT Support | Account lockout, password reset, common issues | 6 |
| `hr_leave_policy.txt` | HR | Remote work policy, probation period, approval | 5 |
| **Total** | - | 5 documents | **29 chunks** |

### Quyết định chunking
| Tham số | Giá trị | Lý do |
|---------|---------|-------|
| Chunk size | 400 tokens (~1600 chars) | Balance: detail sufficient + retrieval flexible |
| Overlap | 80 tokens (~320 chars) | Preserve context at chunk boundaries |
| Chunking strategy | Section-based with paragraph overlap | Split by "===...===" headings first, then by paragraphs |
| Metadata fields | source, section, effective_date, department, access | Enable citation, filtering, freshness checks |
| Tokenizer | character-based (approx 1 char = 0.25 tokens) | Fast, language-agnostic |

**Implementation note:** Custom `_split_by_size()` splits by section heading ("==="), then by paragraph ("\\n\\n"), preserving natural boundaries.

### Embedding model
- **Model**: `text-embedding-3-small` (OpenAI, 1536-dim)
  - Reason: High-quality multilingual embeddings, supports Vietnamese + English well
  - Configurable via `EMBEDDING_PROVIDER` env var; fallback to `paraphrase-multilingual-MiniLM-L12-v2` (SentenceTransformers) if set to "local"
- **Vector store**: ChromaDB PersistentClient (`chroma_db/`)
- **Similarity metric**: Cosine distance
- **Dimension**: 1536

---

## 3. Retrieval Pipeline (Sprint 2 + 3)

### Baseline (Dense Search)
| Tham số | Giá trị | Performance |
|---------|--------|-------------|
| Strategy | Dense vector search (cosine similarity) | Context Recall: 5.00/5 |
| Top-k search | 10 | Faithfulness: 4.70/5 |
| Top-k select | 3 | Relevance: 4.40/5 |
| Rerank | None | Completeness: 3.70/5 |
| Query transform | None | Evaluated on 10 test questions |

### Variant (Hybrid + LLM Rerank + Query Expansion)
| Tham số | Giá trị | Performance | vs Baseline |
|---------|--------|-------------|-------------|
| Strategy | Hybrid (Dense + BM25 with RRF, k=60) | Context Recall: 5.00/5 | = |
| Top-k search | 10 (dense+sparse merged) | Faithfulness: 4.30/5 | −0.40 |
| Top-k select | 3 (after LLM rerank) | Relevance: 4.30/5 | −0.10 |
| Rerank | LLM-as-Reranker (gpt-4o-mini selects top-3 indices) | Completeness: 3.80/5 | +0.10 |
| Query transform | expansion (2 alias/paraphrase variants, multi-query merge+dedup) | - | - |

**A/B rule applied:** Only `retrieval_mode` was changed from the baseline (dense → hybrid). Rerank and query expansion were added as the Sprint 3 variant package for comparison. Each experiment is documented in `results/ab_comparison.csv`.

---

## 4. Generation (Sprint 2)

### Grounded Prompt Template
```
Answer the question only based on the retrieved context below.
If the context is insufficient or doesn't address the question, explicitly say: "Không tìm thấy thông tin"
Always cite the source document when referencing facts.
Keep answers concise, factual, and grounded.

Question: {query}

Context:
{context_chunks_with_sources}

Answer:
```

### LLM Configuration
| Tham số | Giá trị | Reason |
|---------|--------|--------|
| Model | gpt-4o-mini | Cost-effective, high-quality reasoning, good Vietnamese support |
| Temperature | 0 | Deterministic output for reproducible evaluation |
| Max tokens | 512 | Sufficient for policy Q&A without token waste |
| System prompt | Evidence-only + abstain + citation | Enforce faithfulness, reduce hallucination |

**Evaluated on:**
- 10 test questions (2-3 per category)
- 4 metrics: Faithfulness, Relevance, Context Recall, Completeness
- See `results/scorecard_baseline.md` for detailed results

---

## 5. Known Issues & Failure Modes

### Completeness Gaps
| Issue | Example | Root Cause | Fix |
|-------|---------|-----------|-----|
| Document rename not surfaced | q07: "Access Control SOP" name not mentioned | No chunk states old→new name mapping | Add explicit "DOCUMENT META" chunk per file |
| Error code not documented | q09: ERR-403-AUTH abstain incomplete | No error code reference in any doc | Create error code reference section in IT FAQ |
| Missing policies | q10: VIP refund abstain incomplete | No VIP-specific policy in docs | Abstain prompt should mention standard fallback |

### Retrieval & Generation Quality
| Metric | Baseline | Variant | Status | Bottleneck? |
|--------|----------|---------|--------|-------------|
| Context Recall | 5.00/5 | 5.00/5 | Excellent | No |
| Faithfulness | 4.70/5 | 4.30/5 | Good | Monitor variant regression |
| Relevance | 4.40/5 | 4.30/5 | Good | Minor gap |
| Completeness | 3.70/5 | 3.80/5 | **Bottleneck** | Yes — knowledge base gaps |

### Debug Checklist
| Failure Type | Diagnostic | Tool |
|-------------|-----------|------|
| Index issue | "Retrieved old docs / wrong version" | `list_chunks()` preview, metadata inspection |
| Chunking issue | "Answer cuts off mid-clause" | Manual chunk review in ChromaDB |
| Retrieval issue | "Expected source not retrieved" | `context_recall` metric scoring |
| Generation issue | "Answer fabricated / off-topic" | `faithfulness` metric scoring |
| Context lost | "Long context not used properly" | Check prompt structure, chunk ordering |

---

## 6. System Data Flow

### Indexing Pipeline (Detailed)

```mermaid
---
config:
  layout: dagre
---
flowchart TD
    A[Start: python index.py] --> B[Load .env]
    B --> C[Set config: DOCS_DIR, CHROMA_DB_DIR, CHUNK_SIZE, CHUNK_OVERLAP]
    C --> D[List all .txt files in data/docs]
    D --> E[Read raw text từng file]

    E --> F["preprocess_document()"]
    F --> F1["Parse metadata header<br/>Source, Department, Effective Date, Access"]
    F1 --> F2["Remove header lines<br/>Clean text"]
    F2 --> G["chunk_document()"]

    G --> G1["Split by section heading<br/>=== ... ==="]
    G1 --> G2["_split_by_size()"]
    G2 --> G3[Split by paragraph]
    G3 --> G4[Add overlap between chunks]
    G4 --> H["Chunks with metadata<br/>source, section, department, effective_date, access"]

    H --> I["get_embedding(chunk_text)"]
    I --> J{Embedding provider?}
    J -->|openai| J1[OpenAI text-embedding-3-small]
    J -->|local| J2[SentenceTransformer local model]

    J1 --> K[ChromaDB PersistentClient]
    J2 --> K
    K --> L[Get or create collection rag_lab]
    L --> M[Upsert chunk id + embedding + document + metadata]
    M --> N[Repeat for all chunks/files]
    N --> O["list_chunks()"]
    N --> P["inspect_metadata_coverage()"]
    P --> Q[End: index built]
```

**Output:** 24 chunks indexed in ChromaDB with metadata

---

### Generation & Retrieval Pipeline (Detailed)

```mermaid
---
config:
  layout: dagre
---
flowchart TD
    A["Start: rag_answer(query)"] --> B[Choose retrieval_mode]
    B --> C{Mode?}

    C -->|dense| D1["retrieve_dense()"]
    C -->|sparse| D2["retrieve_sparse()"]
    C -->|hybrid| D3["retrieve_hybrid()"]

    D1 --> E[Candidate chunks]
    D2 --> E
    D3 --> E

    E --> F{use_rerank?}
    F -->|Yes| G["rerank(candidates)"]
    F -->|No| H[Take top_k_select candidates]

    G --> H
    H --> I["build_context_block()"]
    I --> I1["Format chunks as<br/>[1] source | section | score"]
    I1 --> J["build_grounded_prompt()"]

    J --> J1["Prompt rule:<br/>Answer only from context<br/>Say you do not know if insufficient<br/>Cite sources"]
    J1 --> K["call_llm()"]
    K --> L[LLM generates answer]

    L --> M[Extract sources from chunks_used]
    M --> N[Return result dict]
    N --> N1[answer]
    N --> N2[sources]
    N --> N3[chunks_used]
    N --> N4[config]

    N --> O["Used by app.py / eval.py"]

    subgraph Details["Retrieval Details"]
        D1a["Dense: query embedding -> ChromaDB cosine search"]
        D2a["Sparse: BM25 keyword search"]
        D3a["Hybrid: Dense + Sparse -> RRF fusion"]
    end
```

**Output:** Grounded answer + sources + metadata

---

### Evaluation Pipeline

```
Generated Answers → eval.py → Score 4 metrics (F/R/CR/Comp)
                                    ↓
                            ab_comparison.csv
                                    ↓
                    Generate reports (scorecard_*.md)
                                    ↓
                    Track metrics (baseline_tracking.csv)
```

### Pipeline Entry Points
- **Build index**: `python index.py` (creates ChromaDB)
- **Evaluate**: `python eval.py` → generates `ab_comparison.csv`
- **Generate answers**: `python rag_answer.py <question>` → grounded response
- **Track metrics**: `python save_baseline.py` → `baseline_tracking.csv`
- **Generate reports**: `python generate_scorecard.py` → `scorecard_*.md`

---

## 7. Performance Summary (as of 2026-04-13)

**Baseline Configuration:**
```
Embedding: text-embedding-3-small (OpenAI, 1536-dim)
Chunking: 400 tokens, 80 overlap, section-based
Retrieval: Dense (top-k search=10, select=3), no rerank
Generation: gpt-4o-mini, temperature=0, grounded prompt
```

**Baseline Results (10 test questions):**
| Metric | Score | Status |
|--------|-------|--------|
| Faithfulness | 4.70/5 | Strong |
| Relevance | 4.40/5 | Good |
| Context Recall | 5.00/5 | Perfect |
| Completeness | 3.70/5 | **Needs work** |
| Overall | **4.45/5** | Good baseline |

**Variant Results (Hybrid + Rerank + Query Expansion):**
| Metric | Score | Delta |
|--------|-------|-------|
| Faithfulness | 4.30/5 | −0.40 |
| Relevance | 4.30/5 | −0.10 |
| Context Recall | 5.00/5 | 0.00 |
| Completeness | 3.80/5 | **+0.10** |

**Key finding:** Hybrid+rerank+expansion improves Completeness (+0.10) — the pipeline retrieves more edge-case detail — but slightly hurts Faithfulness (−0.40) because conflicting context from BM25 can confuse generation on ambiguous queries (e.g., q03 Level 3 approval path).

See `docs/tuning-log.md` for detailed A/B test results.
