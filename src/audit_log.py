from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class AuditEvent:
    run_id: str
    timestamp: float
    event: str
    input_hash: str
    store_name: str
    document_id: str
    status: str
    prompt_version: str = "ppt-google-file-search-v1"
    model_version: str = "gemini-3.7-flash"
    rule_version: str = "2026.1"


def hash_input(value: bytes | str) -> str:
    payload = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def new_event(event: str, value: bytes | str, store_name: str = "", document_id: str = "", status: str = "OK") -> AuditEvent:
    return AuditEvent(
        run_id=str(uuid.uuid4()),
        timestamp=time.time(),
        event=event,
        input_hash=hash_input(value),
        store_name=store_name,
        document_id=document_id,
        status=status,
    )


def append_jsonl(path: Path, event: AuditEvent, extra: dict[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    record = asdict(event)
    if extra:
        record.update(extra)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

