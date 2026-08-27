from __future__ import annotations

import time
from typing import NamedTuple
from google import genai
from google.genai import types


class RAGResult(NamedTuple):
    answer: str
    status: str
    citations: list
    model: str
    store_name: str
    metadata_filter: str


def make_client(api_key: str) -> genai.Client:
    """google-genai v2.0+ 최신 표준 클라이언트 생성"""
    return genai.Client(api_key=api_key)


def create_store(client: genai.Client, display_name: str) -> str:
    """Google File Search Store(Vector Store) 생성"""
    store = client.files.create_vector_store(
        config=types.CreateVectorStoreConfig(display_name=display_name)
    )
    return store.name


def upload_and_wait(
    client: genai.Client,
    store_name: str,
    filename: str,
    file_bytes: bytes,
    document_id: str,
    role: str,
    regulation_version: str,
    effective_date: str,
) -> str:
    """문서 업로드, 메타데이터 부여 및 Vector Store 색인 완료 대기"""
    # 1. 파일 업로드 및 메타데이터 필터 설정
    metadata = [
        types.CustomMetadata(key="document_id", string_value=document_id),
        types.CustomMetadata(key="role", string_value=role),
        types.CustomMetadata(key="regulation_version", string_value=regulation_version),
        types.CustomMetadata(key="effective_date", string_value=effective_date),
    ]

    uploaded_file = client.files.upload(
        file=file_bytes,
        config=types.UploadFileConfig(
            display_name=filename,
            mime_type="application/pdf" if filename.endswith(".pdf") else "text/plain",
        ),
    )

    # 2. Vector Store에 파일 바인딩 및 색인
    client.files.create_vector_store_file(
        vector_store=store_name,
        file=uploaded_file.name,
        config=types.CreateVectorStoreFileConfig(custom_metadata=metadata),
    )

    # 3. 색인 처리 대기 (Processing 상태 확인)
    while True:
        file_status = client.files.get(name=uploaded_file.name)
        if file_status.state.name == "ACTIVE":
            break
        elif file_status.state.name == "FAILED":
            raise RuntimeError(f"파일 색인 실패: {uploaded_file.name}")
        time.sleep(2)

    return uploaded_file.name


def query(
    client: genai.Client,
    store_name: str,
    question: str,
    role: str,
    regulation_version: str,
) -> RAGResult:
    """메타데이터 필터를 통한 서버 사이드 문서 검색 및 근거 기반 답변 생성"""
    # 메타데이터 필터 바인딩
    filter_expr = f'role == "{role}" AND regulation_version == "{regulation_version}"'
    
    # 최신 v2.0+ File Search Tool 구성
    file_search_tool = types.Tool(
        file_search=types.FileSearch(
            vector_store_names=[store_name],
            filter=filter_expr
        )
    )

    prompt = (
        f"질문: {question}\n\n"
        "반드시 제공된 문서 내용만 근거로 답변하세요. "
        "인용 가능한 정보가 부족하거나 없으면 절대로 임의로 생성하지 말고 '검색 근거가 없습니다.'라고 답변하세요."
    )

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            tools=[file_search_tool],
            temperature=0.0,
        ),
    )

    # File Citation 존재 여부 판별
    citations = []
    has_citation = False

    if response.candidates and response.candidates[0].citation_metadata:
        citation_sources = response.candidates[0].citation_metadata.citation_sources
        if citation_sources:
            has_citation = True
            for src in citation_sources:
                citations.append({
                    "title": getattr(src, "uri", "사규 문서"),
                    "text": getattr(src, "snippet", "인용 본문 내용"),
                })

    # 인용 근거(file_citation)가 없을 경우 답변 보류 처리
    if not has_citation:
        return RAGResult(
            answer="제공된 사규 문서에서 질문에 대한 근거를 찾을 수 없어 답변을 보류합니다.",
            status="PENDING",
            citations=[],
            model="gemini-2.5-flash",
            store_name=store_name,
            metadata_filter=filter_expr,
        )

    return RAGResult(
        answer=response.text,
        status="ANSWERED",
        citations=citations,
        model="gemini-2.5-flash",
        store_name=store_name,
        metadata_filter=filter_expr,
    )
