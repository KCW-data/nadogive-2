from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Citation:
    file_name: str
    page_number: int | None = None
    source: str | None = None
    custom_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SearchResult:
    answer: str
    citations: list[Citation]
    status: str
    store_name: str
    metadata_filter: str
    model: str


@dataclass(frozen=True)
class Finding:
    finding_id: str
    audit_objective: str
    criterion: str
    condition: str
    evidence: list[Citation]
    calculation: str
    risk_level: str
    recommendation: str
    agent_status: str
    auditor_decision: str = "PENDING"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [item.to_dict() for item in self.evidence]
        return data

