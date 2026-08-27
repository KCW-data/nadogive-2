from __future__ import annotations

import re


ALLOWED_ROLES = {"auditor", "manager", "public"}
SAFE_METADATA_VALUE = re.compile(r"^[0-9A-Za-z._-]{1,80}$")


class SecurityError(ValueError):
    pass


def validate_store_name(store_name: str) -> str:
    value = store_name.strip()
    if not value.startswith("fileSearchStores/") or len(value) > 180:
        raise SecurityError("Store 이름은 fileSearchStores/... 형식이어야 합니다.")
    if not re.fullmatch(r"fileSearchStores/[0-9A-Za-z_-]+", value):
        raise SecurityError("Store 이름에 허용되지 않은 문자가 있습니다.")
    return value


def validate_metadata_value(value: str, field: str) -> str:
    cleaned = value.strip()
    if not SAFE_METADATA_VALUE.fullmatch(cleaned):
        raise SecurityError(f"{field} 값은 영문, 숫자, 점, 밑줄, 하이픈만 사용할 수 있습니다.")
    return cleaned


def build_metadata_filter(role: str, regulation_version: str) -> str:
    """Build a filter only from server-controlled allowlisted values."""
    if role not in ALLOWED_ROLES:
        raise SecurityError("허용되지 않은 역할입니다.")
    version = validate_metadata_value(regulation_version, "regulation_version")
    return f'role="{role}" AND regulation_version="{version}"'


def ensure_store_allowed(store_name: str, allowlist: list[str]) -> str:
    checked = validate_store_name(store_name)
    normalized = {validate_store_name(item) for item in allowlist if item.strip()}
    if checked not in normalized:
        raise SecurityError("이 앱에 허용된 File Search Store가 아닙니다.")
    return checked

