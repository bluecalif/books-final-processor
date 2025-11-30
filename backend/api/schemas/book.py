"""책 관련 Pydantic 스키마"""
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from backend.api.models.book import BookStatus


class BookResponse(BaseModel):
    """책 응답 스키마"""
    id: int
    title: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None  # 분야 (예: 역사/사회, 경제/경영 등)
    source_file_path: str
    page_count: Optional[int] = None
    status: BookStatus
    structure_data: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }


class BookListResponse(BaseModel):
    """책 리스트 응답 스키마"""
    books: List[BookResponse]
    total: int


class BookCreate(BaseModel):
    """책 생성 스키마 (업로드용)"""
    title: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None  # 분야 (예: 역사/사회, 경제/경영 등)


class PageSummaryResponse(BaseModel):
    """페이지 요약 응답 스키마"""
    id: int
    book_id: int
    page_id: Optional[int] = None
    page_number: int
    summary_text: str
    structured_data: Optional[dict] = None  # 구조화된 엔티티 데이터 (도메인별 스키마)
    lang: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }


class ChapterSummaryResponse(BaseModel):
    """챕터 요약 응답 스키마"""
    id: int
    book_id: int
    chapter_id: int
    summary_text: str
    structured_data: Optional[dict] = None  # 구조화된 엔티티 데이터 (도메인별 스키마)
    lang: Optional[str] = None
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }
