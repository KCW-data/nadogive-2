from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


REQUIRED_COLUMNS = {"transaction_id", "card_id", "employee_id", "paid_at", "merchant", "amount"}


class ExpenseDataError(ValueError):
    pass


@dataclass(frozen=True)
class ExpenseAnalysis:
    transactions: pd.DataFrame
    alerts: pd.DataFrame
    split_sessions: pd.DataFrame


def validate_transactions(raw: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(raw.columns))
    if missing:
        raise ExpenseDataError("필수 열 누락: " + ", ".join(missing))
    frame = raw.copy()
    for column in ["transaction_id", "card_id", "employee_id", "merchant"]:
        frame[column] = frame[column].astype(str).str.strip()
        if frame[column].eq("").any():
            rows = (frame.index[frame[column].eq("")] + 2).tolist()
            raise ExpenseDataError(f"{column} 빈 값: CSV 행 {rows}")
    duplicates = frame.loc[frame["transaction_id"].duplicated(keep=False), "transaction_id"].unique().tolist()
    if duplicates:
        raise ExpenseDataError("중복 transaction_id: " + ", ".join(map(str, duplicates)))
    frame["paid_at"] = pd.to_datetime(frame["paid_at"], errors="coerce")
    if frame["paid_at"].isna().any():
        rows = (frame.index[frame["paid_at"].isna()] + 2).tolist()
        raise ExpenseDataError(f"paid_at 날짜 변환 실패: CSV 행 {rows}")
    frame["amount"] = pd.to_numeric(frame["amount"], errors="coerce")
    if frame["amount"].isna().any() or frame["amount"].le(0).any():
        rows = (frame.index[frame["amount"].isna() | frame["amount"].le(0)] + 2).tolist()
        raise ExpenseDataError(f"amount는 0보다 큰 숫자여야 합니다: CSV 행 {rows}")
    frame["merchant_key"] = frame["merchant"].str.upper().str.replace(r"\s+", " ", regex=True)
    return frame


def is_night(value: pd.Timestamp) -> bool:
    return value.hour >= 22 or value.hour <= 5


def detect_split_sessions(frame: pd.DataFrame, minutes: int = 30, threshold: float = 500_000) -> pd.DataFrame:
    ordered = frame.sort_values(["card_id", "merchant_key", "paid_at", "transaction_id"]).copy()
    gap = ordered.groupby(["card_id", "merchant_key"])["paid_at"].diff().dt.total_seconds().div(60)
    ordered["new_session"] = gap.isna() | gap.gt(minutes)
    ordered["session_number"] = ordered.groupby(["card_id", "merchant_key"])["new_session"].cumsum()
    grouped = (
        ordered.groupby(["card_id", "merchant_key", "session_number"], as_index=False)
        .agg(
            first=("paid_at", "min"),
            last=("paid_at", "max"),
            count=("transaction_id", "size"),
            total=("amount", "sum"),
            evidence=("transaction_id", lambda values: " | ".join(map(str, values))),
        )
    )
    alerts = grouped.loc[grouped["count"].ge(2) & grouped["total"].ge(threshold)].copy()
    alerts["session_id"] = alerts.apply(
        lambda row: f"{row.card_id}:{row.merchant_key}:{int(row.session_number)}", axis=1
    )
    return alerts


def _approved_exception_mask(frame: pd.DataFrame, exceptions: pd.DataFrame | None) -> pd.Series:
    mask = pd.Series(False, index=frame.index)
    if exceptions is None or exceptions.empty:
        return mask
    required = {"employee_id", "start_date", "end_date"}
    missing = required - set(exceptions.columns)
    if missing:
        raise ExpenseDataError("승인 예외 CSV 필수 열 누락: " + ", ".join(sorted(missing)))
    exc = exceptions.copy()
    exc["start_date"] = pd.to_datetime(exc["start_date"], errors="raise").dt.date
    exc["end_date"] = pd.to_datetime(exc["end_date"], errors="raise").dt.date
    for _, row in exc.iterrows():
        mask |= frame["employee_id"].eq(str(row["employee_id"]).strip()) & frame["paid_at"].dt.date.between(row["start_date"], row["end_date"])
    return mask


def analyze_expenses(raw: pd.DataFrame, exceptions: pd.DataFrame | None = None) -> ExpenseAnalysis:
    frame = validate_transactions(raw)
    frame["R_WEEKEND"] = frame["paid_at"].dt.dayofweek.ge(5)
    frame["R_NIGHT"] = frame["paid_at"].map(is_night)
    sessions = detect_split_sessions(frame)
    split_ids: set[str] = set()
    if not sessions.empty:
        split_ids = set(" | ".join(sessions["evidence"]).split(" | "))
    frame["R_SPLIT"] = frame["transaction_id"].astype(str).isin(split_ids)
    rule_columns = ["R_WEEKEND", "R_NIGHT", "R_SPLIT"]
    frame["rule_id"] = frame.apply(lambda row: " | ".join(name for name in rule_columns if bool(row[name])), axis=1)
    frame["calculation_basis"] = frame.apply(
        lambda row: f"요일={row.paid_at.day_name()}, 시각={row.paid_at:%H:%M}, 금액={row.amount:,.0f}", axis=1
    )
    frame["approved_exception"] = _approved_exception_mask(frame, exceptions)
    frame["status"] = "NORMAL"
    alerted = frame["rule_id"].ne("")
    frame.loc[alerted, "status"] = "ALERT"
    frame.loc[alerted & frame["approved_exception"], "status"] = "APPROVED_EXCEPTION"
    alerts = frame.loc[alerted].copy()
    return ExpenseAnalysis(frame, alerts, sessions)

