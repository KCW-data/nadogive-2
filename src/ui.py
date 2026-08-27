from __future__ import annotations

from typing import Any

import streamlit as st


def apply_page(title: str, icon: str) -> None:
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    st.markdown(
        """
        <style>
        .block-container {padding-top: 2rem; padding-bottom: 4rem; max-width: 1180px;}
        [data-testid="stMetric"] {background:#f6f8fb; border:1px solid #e3e8ef; padding:14px; border-radius:12px;}
        .audit-note {border-left:4px solid #2d6cdf; padding:10px 14px; background:#f4f7ff; border-radius:4px;}
        code {font-size:.9em;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def read_secret(name: str, default: str = "") -> str:
    try:
        value: Any = st.secrets.get(name, default)
    except Exception:
        value = default
    return str(value or "")


def mode_selector() -> str:
    has_key = bool(read_secret("GEMINI_API_KEY"))
    default_index = 0 if has_key else 1
    mode = st.sidebar.radio(
        "실행 모드",
        ["Google File Search", "교육용 데모"],
        index=default_index,
        help="데모 모드는 API 키 없이 sample_data만 검색합니다.",
    )
    if mode == "Google File Search" and not has_key:
        st.sidebar.error("GEMINI_API_KEY가 없습니다.")
    elif mode == "교육용 데모":
        st.sidebar.warning("로컬 키워드 검색입니다. 실제 RAG 검증에는 Google 모드를 사용하세요.")
    return mode


def show_citations(citations: list[Any]) -> None:
    st.subheader("근거 인용")
    if not citations:
        st.warning("file_citation이 없어 판단을 보류합니다.")
        return
    for number, citation in enumerate(citations, 1):
        page = citation.page_number if citation.page_number is not None else "페이지 정보 없음"
        with st.expander(f"[{number}] {citation.file_name} · {page}", expanded=True):
            st.write({"source": citation.source, "metadata": citation.custom_metadata})

