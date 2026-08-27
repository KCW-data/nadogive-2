from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.audit_log import new_event
from src.demo_search import demo_query
from src.file_search import create_store, make_client, query, upload_and_wait
from src.ui import apply_page, mode_selector, read_secret, show_citations


apply_page("실습 2 · 감사 RAG", "🔎")
st.title("실습 2 · Google File Search 감사 RAG")
st.caption("역할·규정 버전 필터를 서버에서 만들고, file_citation이 없으면 답변을 보류합니다.")

mode = mode_selector()
store_name = read_secret("FILE_SEARCH_STORE_NAME")
api_key = read_secret("GEMINI_API_KEY")
if "rag_store_name" not in st.session_state:
    st.session_state.rag_store_name = store_name

with st.sidebar:
    st.header("검색 통제")
    role = st.selectbox("로그인 역할", ["auditor", "manager", "public"])
    regulation_version = st.selectbox("적용 규정 버전", ["2026.1", "2025.2"])
    st.code(st.session_state.rag_store_name or "FILE_SEARCH_STORE_NAME 없음")

with st.expander("사규 문서 준비 · Store 생성 및 PDF 색인", expanded=mode == "Google File Search"):
    if mode == "교육용 데모":
        st.info("데모 모드는 sample_data/travel_expense_policy.txt를 사용합니다.")
    elif not api_key:
        st.error("GEMINI_API_KEY Secret을 먼저 설정하세요.")
    else:
        c1, c2 = st.columns([1.2, 1])
        with c1:
            selected_store = st.text_input("Store 이름", value=st.session_state.rag_store_name, placeholder="fileSearchStores/...")
            if st.button("이 Store 사용", disabled=not selected_store):
                st.session_state.rag_store_name = selected_store.strip()
        with c2:
            display_name = st.text_input("새 Store 표시 이름", value="audit-policy-rag")
            if st.button("새 Store 생성"):
                st.session_state.rag_store_name = create_store(make_client(api_key), display_name)
                st.success(f"생성: {st.session_state.rag_store_name}")
        policy_file = st.file_uploader("사규 PDF/TXT/MD", type=["pdf", "txt", "md"])
        document_id = st.text_input("document_id", value="POLICY-TRAVEL-2026")
        if st.button("사규 업로드·색인", type="primary", disabled=not (policy_file and st.session_state.rag_store_name)):
            with st.spinner("Google File Search 색인 완료까지 대기 중..."):
                doc_name = upload_and_wait(
                    make_client(api_key), st.session_state.rag_store_name, policy_file.name, policy_file.getvalue(),
                    document_id, role, regulation_version, "2026-01-01",
                )
            st.success(f"색인 완료: {doc_name}")
            st.info("생성한 Store 이름을 Streamlit Cloud의 FILE_SEARCH_STORE_NAME Secret에 등록하세요.")

question = st.text_area(
    "감사 질문",
    value="출장비 규정상 숙박비 한도와 증빙 요건은 무엇인가?",
    height=110,
)

if st.button("근거를 검색하고 답변 생성", type="primary", width="stretch"):
    try:
        with st.spinner("문서 검색 및 인용 확인 중..."):
            if mode == "교육용 데모":
                result = demo_query(question, role, regulation_version, ROOT / "sample_data")
            else:
                if not st.session_state.rag_store_name:
                    raise ValueError("FILE_SEARCH_STORE_NAME Secret이 없습니다.")
                result = query(make_client(api_key), st.session_state.rag_store_name, question, role, regulation_version)
        st.session_state.rag_result = result
        st.session_state.rag_event = new_event("AUDIT_RAG_QUERY", question, result.store_name, status=result.status).__dict__
    except Exception as exc:
        st.error(f"요청을 처리하지 못했습니다: {exc}")

result = st.session_state.get("rag_result")
if result:
    m1, m2, m3 = st.columns(3)
    m1.metric("상태", result.status)
    m2.metric("인용 수", len(result.citations))
    m3.metric("모델", result.model)
    if result.status == "ANSWERED":
        st.success(result.answer)
    else:
        st.warning(result.answer or "검색 근거가 없어 판단을 보류합니다.")
    show_citations(result.citations)
    with st.expander("재현 정보"):
        st.code(result.metadata_filter)
        st.json(st.session_state.get("rag_event", {}))

st.markdown('<div class="audit-note">이 결과는 감사 보조 의견입니다. 원문과 인용 페이지를 대조한 뒤 감사인이 최종 판단합니다.</div>', unsafe_allow_html=True)
