"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Các rule nhóm đã thêm (metric_impact ghi ở reports/group_report.md):
  R7 strip_invisible_chars: loại BOM/zero-width khỏi chunk_text trước khi so sánh dedupe.
  R8 quarantine_future_effective_date: effective_date xa hơn cutoff tương lai → quarantine.
  R9 quarantine_chunk_too_long: chunk_text > MAX_CHUNK_LEN → quarantine (tránh context dài bất thường).
  R10 normalize_policy_version_marker: thay "policy-v3" trong refund v4 → "policy-v4".
"""

from __future__ import annotations

import csv
import hashlib
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
    }
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")

# Giới hạn chunk — giữ thấp để lab có thể quarantine inject chunk quá dài.
MAX_CHUNK_LEN = 2000

# Cutoff tương lai: effective_date xa hơn today + 2 năm coi là lỗi export.
FUTURE_DATE_SLACK_DAYS = 365 * 2

# Ký tự "tàng hình" hay gặp khi export sai encoding.
_INVISIBLE_CHARS = ("\ufeff", "\u200b", "\u200c", "\u200d", "\u00a0")


def _strip_invisible(s: str) -> str:
    """R7: loại BOM/zero-width space/nbsp để dedupe + expectation length chính xác."""
    if not s:
        return s
    for ch in _INVISIBLE_CHARS:
        s = s.replace(ch, "")
    return s


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        return s, ""
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}", ""
    return "", "invalid_effective_date_format"


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Baseline (mở rộng theo narrative Day 10):
    1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
    2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
    3) Quarantine: chunk hr_leave_policy có effective_date < 2026-01-01 (bản HR cũ / conflict version).
    4) Quarantine: chunk_text rỗng hoặc effective_date rỗng sau chuẩn hoá.
    5) Loại trùng nội dung chunk_text (giữ bản đầu).
    6) Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.

    Rule nhóm mở rộng:
    R7) Strip ký tự tàng hình (BOM, zero-width) trong chunk_text trước dedupe.
    R8) Quarantine nếu effective_date > today + FUTURE_DATE_SLACK_DAYS (typo export).
    R9) Quarantine nếu chunk_text dài bất thường (> MAX_CHUNK_LEN).
    R10) Normalize marker version trong refund v4: "policy-v3" → "policy-v4".
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    seq = 0
    today = date.today()
    future_cutoff = today + timedelta(days=FUTURE_DATE_SLACK_DAYS)

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        # R7: strip invisible chars ngay khi đọc (ảnh hưởng cả dedupe + length expectation).
        text = _strip_invisible(raw.get("chunk_text", ""))
        eff_raw = raw.get("effective_date", "")
        exported_at = raw.get("exported_at", "")

        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        # R8: effective_date không được xa tương lai (lỗi export kiểu 2099-01-01).
        try:
            eff_d = date.fromisoformat(eff_norm)
            if eff_d > future_cutoff:
                quarantine.append(
                    {
                        **raw,
                        "reason": "future_effective_date",
                        "effective_date_normalized": eff_norm,
                    }
                )
                continue
        except ValueError:
            quarantine.append({**raw, "reason": "invalid_effective_date_format", "effective_date_raw": eff_raw})
            continue

        if doc_id == "hr_leave_policy" and eff_norm < "2026-01-01":
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        if not text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        # R9: chunk quá dài → quarantine (tránh context bất thường làm bẩn top-k).
        if len(text) > MAX_CHUNK_LEN:
            quarantine.append(
                {
                    **raw,
                    "reason": "chunk_too_long",
                    "chunk_len": len(text),
                }
            )
            continue

        key = _norm_text(text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        fixed_text = text
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            if "14 ngày làm việc" in fixed_text:
                fixed_text = fixed_text.replace(
                    "14 ngày làm việc",
                    "7 ngày làm việc",
                )
                fixed_text += " [cleaned: stale_refund_window]"

        # R10: normalize marker version cũ còn sót trong refund v4.
        if doc_id == "policy_refund_v4" and "policy-v3" in fixed_text:
            fixed_text = fixed_text.replace("policy-v3", "policy-v4")

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
