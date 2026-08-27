from __future__ import annotations

import re
from pathlib import Path

from .models import Citation, SearchResult
from .security import build_metadata_filter


def demo_query(question: str, role: str, regulation_version: str, sample_dir: Path) -> SearchResult:
    metadata_filter = build_metadata_filter(role, regulation_version)
    terms = {term.lower() for term in re.findall(r"[0-9A-Za-z가-힣]{2,}", question)}
    candidates: list[tuple[int, Path, str]] = []
    for path in sample_dir.glob("*.txt"):
        text = path.read_text(encoding="utf-8")
        score = sum(text.lower().count(term) for term in terms)
        candidates.append((score, path, text))
    candidates.sort(key=lambda row: row[0], reverse=True)
    if not candidates or candidates[0][0] == 0:
        return SearchResult(
            "샘플 문서에서 질문과 관련된 근거를 찾지 못했습니다.", [], "INSUFFICIENT", "demo-store", metadata_filter, "demo-local"
        )
    _, path, text = candidates[0]
    lines = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    matched = [line for line in lines if any(term in line.lower() for term in terms)] or lines[:3]
    answer = "교육용 데모 검색 결과입니다.\n\n" + "\n".join(f"- {line}" for line in matched[:4])
    citation = Citation(path.name, 1, f"sample_data/{path.name}", {"role": role, "regulation_version": regulation_version})
    return SearchResult(answer, [citation], "ANSWERED", "demo-store", metadata_filter, "demo-local")

