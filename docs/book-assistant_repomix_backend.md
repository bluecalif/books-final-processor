This file is a merged representation of a subset of the codebase, containing specifically included files and files not matching ignore patterns, combined into a single document by Repomix.
The content has been processed where security check has been disabled.

# File Summary

## Purpose
This file contains a packed representation of a subset of the repository's contents that is considered the most important context.
It is designed to be easily consumable by AI systems for analysis, code review,
or other automated processes.

## File Format
The content is organized as follows:
1. This summary section
2. Repository information
3. Directory structure
4. Repository files (if enabled)
5. Multiple file entries, each consisting of:
  a. A header with the file path (## File: path/to/file)
  b. The full contents of the file in a code block

## Usage Guidelines
- This file should be treated as read-only. Any changes should be made to the
  original repository files, not this packed version.
- When processing this file, use the file path to distinguish
  between different files in the repository.
- Be aware that this file may contain sensitive information. Handle it with
  the same level of security as you would the original repository.

## Notes
- Some files may have been excluded based on .gitignore rules and Repomix's configuration
- Binary files are not included in this packed representation. Please refer to the Repository Structure section for a complete list of file paths, including binary files
- Only files matching these patterns are included: backend/**, frontend/**
- Files matching these patterns are excluded: backend/tests/**, docs/**, cache/**, output/**
- Files matching patterns in .gitignore are excluded
- Files matching default ignore patterns are excluded
- Security check has been disabled - content may contain sensitive information
- Files are sorted by Git change count (files with more changes are at the bottom)

# Directory Structure
```
backend/
  api/
    models/
      __init__.py
      base.py
      book.py
    routers/
      __init__.py
      books.py
      search.py
      structure.py
      summary.py
    schemas/
      __init__.py
      book.py
      search.py
      summary.py
    services/
      __init__.py
      book_service.py
      search_service.py
      structure_service.py
      summary_service.py
    __init__.py
    database.py
    dependencies.py
    main.py
  config/
    constants.py
    settings.py
  parsers/
    cache_manager.py
    layout_analyzer.py
    page_splitter.py
    pdf_parser.py
    text_processor.py
    upstage_api_client.py
  search/
    search_service.py
  storage/
    document_builder.py
    hierarchical_vector_store.py
  structure/
    chapter_detector.py
    content_boundary_detector.py
    footer_analyzer.py
    hierarchy_builder.py
    structure_builder.py
  summarizers/
    batch_processor.py
    chapter_merger.py
    document_loaders.py
    hierarchical_summarizer.py
    llm_chains.py
    node_summarizer.py
    page_splitter.py
    page_summarizer.py
    page_summary_cache.py
  utils/
    convert_gt_csv_to_json.py
frontend/
  app/
    books/
      [id]/
        page.tsx
    globals.css
    layout.tsx
    page.tsx
  components/
    ui/
      accordion.tsx
      alert.tsx
      badge.tsx
      button.tsx
      card.tsx
      input.tsx
      progress.tsx
      tabs.tsx
    BookCard.tsx
    BookHeader.tsx
    BookList.tsx
    ChapterSummaryView.tsx
    PageSummaryView.tsx
    providers.tsx
    SearchBar.tsx
    SearchResults.tsx
    SearchViewer.tsx
    StatusBadge.tsx
    StructureViewer.tsx
    SummaryViewer.tsx
    UploadZone.tsx
  hooks/
    useBooks.ts
    useSearch.ts
    useStructure.ts
    useSummary.ts
  public/
    file.svg
    globe.svg
    next.svg
    vercel.svg
    window.svg
  types/
    api.ts
  .gitignore
  next.config.ts
  postcss.config.mjs
  README.md
```

# Files

## File: backend/api/models/__init__.py
````python
"""
SQLAlchemy ORM 모델
"""
from .book import Book, Chapter, Summary, BookStatus

__all__ = ["Book", "Chapter", "Summary", "BookStatus"]
````

## File: backend/api/models/base.py
````python
"""
SQLAlchemy Base 클래스

모든 ORM 모델의 부모 클래스
"""
from backend.api.database import Base

__all__ = ["Base"]
````

## File: backend/api/models/book.py
````python
"""
Book 관련 SQLAlchemy ORM 모델

Book, Chapter, Summary 테이블 정의
"""
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .base import Base


class BookStatus(str, enum.Enum):
    """책 처리 상태"""
    UPLOADED = "uploaded"           # 업로드 완료
    ANALYZING = "analyzing"         # 구조 분석 중
    ANALYZED = "analyzed"           # 구조 분석 완료
    SUMMARIZING = "summarizing"     # 요약 생성 중
    COMPLETED = "completed"         # 전체 완료
    FAILED = "failed"              # 실패


class Book(Base):
    """
    책 정보 테이블
    
    업로드된 PDF 파일의 메타데이터와 처리 상태 관리
    """
    __tablename__ = "books"
    
    # 기본 정보
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    title = Column(String, nullable=True)
    
    # 파일 정보
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    total_pages = Column(Integer, nullable=True)
    
    # 처리 상태
    status = Column(SQLEnum(BookStatus), default=BookStatus.UPLOADED, nullable=False)
    error_message = Column(String, nullable=True)
    
    # 타임스탬프
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    analyzed_at = Column(DateTime, nullable=True)
    summarized_at = Column(DateTime, nullable=True)
    
    # 구조 분석 결과 (JSON 저장)
    structure_data = Column(JSON, nullable=True)
    
    # 관계 (cascade: 책 삭제 시 챕터, 요약도 함께 삭제)
    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan")
    summaries = relationship("Summary", back_populates="book", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Book(id={self.id}, filename='{self.filename}', status='{self.status.value}')>"


class Chapter(Base):
    """
    챕터 정보 테이블
    
    구조 분석 결과로부터 추출된 챕터 정보 저장
    """
    __tablename__ = "chapters"
    
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    
    # 챕터 정보
    chapter_num = Column(Integer, nullable=False)
    chapter_id = Column(String, nullable=False)  # ch1, ch2, ...
    title = Column(String, nullable=False)
    start_page = Column(Integer, nullable=False)
    end_page = Column(Integer, nullable=False)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 관계
    book = relationship("Book", back_populates="chapters")
    summaries = relationship("Summary", back_populates="chapter")
    
    def __repr__(self):
        return f"<Chapter(id={self.id}, title='{self.title}', pages={self.start_page}-{self.end_page})>"


class Summary(Base):
    """
    요약 정보 테이블
    
    책 또는 챕터별 요약 데이터 저장 (JSON 형식)
    """
    __tablename__ = "summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=True)
    
    # 요약 데이터 (JSON 저장)
    # {facts: [], claims: [], examples: [], keywords: [], summary: "..."}
    summary_data = Column(JSON, nullable=False)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 관계
    book = relationship("Book", back_populates="summaries")
    chapter = relationship("Chapter", back_populates="summaries")
    
    def __repr__(self):
        return f"<Summary(id={self.id}, book_id={self.book_id}, chapter_id={self.chapter_id})>"
````

## File: backend/api/routers/__init__.py
````python
"""
API 라우터
"""
from . import books, structure, summary, search

__all__ = ["books", "structure", "summary", "search"]
````

## File: backend/api/routers/books.py
````python
"""
Books API Router

책 파일 관리 관련 API 엔드포인트
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import shutil
from pathlib import Path
from datetime import datetime

from backend.api.database import get_db
from backend.api.models.book import Book, BookStatus
from backend.api.schemas.book import (
    BookUploadResponse,
    BookListResponse,
    BookDetailResponse,
)

router = APIRouter(prefix="/api/books", tags=["books"])


@router.post("/upload", response_model=BookUploadResponse)
async def upload_book(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    PDF 파일 업로드
    
    - **file**: PDF 파일 (multipart/form-data)
    
    Returns:
        BookUploadResponse: 업로드된 책 정보
    """
    # PDF 파일 검증
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # 업로드 디렉토리 생성
    upload_dir = Path("cache/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # 고유한 파일명 생성 (타임스탬프 포함)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = upload_dir / safe_filename
    
    # 파일 저장
    with file_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    file_size = file_path.stat().st_size
    
    # DB에 책 정보 저장
    book = Book(
        filename=safe_filename,
        original_filename=file.filename,
        file_path=str(file_path),
        file_size=file_size,
        status=BookStatus.UPLOADED
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    
    return book


@router.get("", response_model=List[BookListResponse])
async def list_books(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    업로드된 책 목록 조회
    
    - **skip**: 건너뛸 항목 수 (페이지네이션)
    - **limit**: 반환할 최대 항목 수
    
    Returns:
        List[BookListResponse]: 책 목록
    """
    books = db.query(Book).order_by(Book.uploaded_at.desc()).offset(skip).limit(limit).all()
    return books


@router.get("/{book_id}", response_model=BookDetailResponse)
async def get_book(
    book_id: int,
    db: Session = Depends(get_db)
):
    """
    책 상세 정보 조회
    
    - **book_id**: 책 ID
    
    Returns:
        BookDetailResponse: 책 상세 정보 (챕터 포함)
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    return book


@router.delete("/{book_id}")
async def delete_book(
    book_id: int,
    db: Session = Depends(get_db)
):
    """
    책 삭제
    
    - **book_id**: 책 ID
    
    Returns:
        dict: 삭제 완료 메시지
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # 파일 삭제
    file_path = Path(book.file_path)
    if file_path.exists():
        file_path.unlink()
    
    # DB에서 삭제 (cascade로 chapters, summaries도 자동 삭제됨)
    db.delete(book)
    db.commit()
    
    return {"message": "Book deleted successfully", "book_id": book_id}
````

## File: backend/api/routers/search.py
````python
"""
Search API Router

검색 관련 API 엔드포인트
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.api.database import get_db
from backend.api.schemas.search import (
    SearchRequest,
    SearchResponse,
    SearchResultDrilldown,
)
from backend.api.services import SearchService as APISearchService

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search_content(request: SearchRequest, db: Session = Depends(get_db)):
    """
    벡터 검색 (chapter/page/drilldown 모드)

    - **query**: 검색 쿼리 (1-500자)
    - **mode**: 검색 모드
        - `chapter`: 챕터만 검색
        - `page`: 페이지만 검색
        - `drilldown`: 챕터 → 페이지 계층 탐색 (기본값)
    - **k**: 반환할 결과 개수 (1-20, 기본값 5)

    Returns:
        SearchResponse: 검색 결과 목록

    Note:
        Phase 3.1.5에서 실제 벡터 검색 로직 연결
    """
    # 서비스 레이어에서 검색 실행
    search_service = APISearchService(db)
    results = search_service.search(query=request.query, mode=request.mode, k=request.k)

    # SearchResultDrilldown으로 변환
    result_items = [SearchResultDrilldown(**r) for r in results]

    return SearchResponse(mode=request.mode, results=result_items)


@router.get("/keywords")
async def search_by_keywords(
    q: str = Query(..., min_length=1, max_length=100, description="검색 키워드"),
    book_id: int = Query(None, description="특정 책으로 제한 (선택)"),
    db: Session = Depends(get_db),
):
    """
    키워드 검색 (메타데이터 기반, 비용 0)

    - **q**: 검색 키워드
    - **book_id**: 특정 책으로 제한 (선택)

    Returns:
        dict: 검색 결과

    Note:
        벡터 검색과 달리 DB 쿼리만 사용하므로 API 비용 없음
        Phase 3.1.5에서 실제 키워드 검색 로직 연결
    """
    # 서비스 레이어에서 키워드 검색 실행
    search_service = APISearchService(db)
    results = search_service.search_by_keywords(query=q, book_id=book_id)

    return {"query": q, "book_id": book_id, "results": results}
````

## File: backend/api/routers/structure.py
````python
"""
Structure Analysis API Router

책 구조 분석 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
import logging

from backend.api.database import get_db
from backend.api.models.book import Book, BookStatus
from backend.api.schemas.book import BookDetailResponse, BookStructureResponse
from backend.api.services import StructureService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["structure"])


@router.post("/{book_id}/analyze", response_model=BookDetailResponse)
async def analyze_structure(
    book_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    구조 분석 시작 (비동기 처리)
    
    - **book_id**: 책 ID
    
    Returns:
        BookDetailResponse: 상태가 'analyzing'으로 변경된 책 정보
    
    Note:
        실제 분석은 백그라운드에서 진행되며, 
        GET /api/books/{id}로 진행 상황을 확인할 수 있습니다.
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if book.status != BookStatus.UPLOADED:
        raise HTTPException(
            status_code=400,
            detail=f"Book already analyzed or in progress. Current status: {book.status.value}"
        )
    
    # 상태를 ANALYZING으로 변경
    book.status = BookStatus.ANALYZING
    db.commit()
    db.refresh(book)
    
    # 서비스 레이어에서 백그라운드 작업 실행
    structure_service = StructureService(db)
    background_tasks.add_task(structure_service.analyze_book_structure, book_id)
    
    return book


@router.get("/{book_id}/structure")  # response_model 임시 제거
async def get_structure(
    book_id: int,
    db: Session = Depends(get_db)
):
    """
    구조 분석 결과 조회
    
    - **book_id**: 책 ID
    
    Returns:
        BookStructureResponse: 구조 분석 결과 (intro, chapters, notes)
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if book.status == BookStatus.UPLOADED:
        raise HTTPException(
            status_code=400,
            detail="Book not analyzed yet. Please call POST /api/books/{id}/analyze first"
        )
    
    if book.status == BookStatus.ANALYZING:
        raise HTTPException(
            status_code=202,
            detail="Structure analysis in progress. Please try again later"
        )
    
    if not book.structure_data:
        raise HTTPException(status_code=404, detail="Structure data not found")
    
    # 내부 구조를 API 친화적 형식으로 변환
    structure = book.structure_data
    
    # 디버그 로그
    logger.info(f"[GET /structure] book_id={book_id}, structure keys={list(structure.keys()) if structure else 'None'}")
    
    result = {
        "intro": structure.get("start", {}).get("pages", []),
        "chapters": structure.get("main", {}).get("chapters", []),
        "notes": structure.get("end", {}).get("pages", [])
    }
    
    logger.info(f"[GET /structure] Returning: intro={len(result['intro'])}, chapters={len(result['chapters'])}, notes={len(result['notes'])}")
    
    return result
````

## File: backend/api/routers/summary.py
````python
"""
Summary API Router

책 요약 생성 관련 API 엔드포인트
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from backend.api.database import get_db
from backend.api.models.book import Book, Chapter, Summary, BookStatus
from backend.api.schemas.summary import (
    BookSummaryResponse,
    ChapterSummaryResponse,
)
from backend.api.services import SummaryService

router = APIRouter(prefix="/api/books", tags=["summary"])


@router.post("/{book_id}/summarize")
async def summarize_book(
    book_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    요약 생성 시작 (비동기 처리)
    
    - **book_id**: 책 ID
    
    Returns:
        dict: 요약 생성 시작 메시지
    
    Note:
        실제 요약은 백그라운드에서 진행되며,
        GET /api/books/{id}로 진행 상황을 확인할 수 있습니다.
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if book.status != BookStatus.ANALYZED:
        raise HTTPException(
            status_code=400,
            detail=f"Book not analyzed yet. Current status: {book.status.value}"
        )
    
    # 상태를 SUMMARIZING으로 변경
    book.status = BookStatus.SUMMARIZING
    db.commit()
    
    # 서비스 레이어에서 백그라운드 작업 실행
    summary_service = SummaryService(db)
    background_tasks.add_task(summary_service.summarize_book, book_id)
    
    return {"message": "Summary generation started", "book_id": book_id}


@router.get("/{book_id}/summary", response_model=BookSummaryResponse)
async def get_book_summary(
    book_id: int,
    db: Session = Depends(get_db)
):
    """
    책 전체 요약 조회
    
    - **book_id**: 책 ID
    
    Returns:
        BookSummaryResponse: 책 전체 요약 (모든 챕터 포함)
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    if book.status != BookStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Summary not completed yet. Current status: {book.status.value}"
        )
    
    # Summary 테이블에서 챕터별 요약 조회
    summaries = db.query(Summary).filter(
        Summary.book_id == book_id,
        Summary.chapter_id.isnot(None)
    ).all()
    
    if not summaries:
        raise HTTPException(status_code=404, detail="Summary data not found")
    
    # ChapterSummaryResponse 형식으로 변환
    chapter_summaries = []
    for summary in summaries:
        chapter = db.query(Chapter).filter(Chapter.id == summary.chapter_id).first()
        if chapter:
            chapter_summaries.append(
                ChapterSummaryResponse(
                    chapter_id=chapter.chapter_id,
                    title=chapter.title,
                    **summary.summary_data
                )
            )
    
    return BookSummaryResponse(
        book_id=book_id,
        chapters=chapter_summaries
    )


@router.get("/{book_id}/chapters/{chapter_id}/summary", response_model=ChapterSummaryResponse)
async def get_chapter_summary(
    book_id: int,
    chapter_id: str,
    db: Session = Depends(get_db)
):
    """
    챕터별 요약 조회
    
    - **book_id**: 책 ID
    - **chapter_id**: 챕터 ID (예: ch1, ch2)
    
    Returns:
        ChapterSummaryResponse: 챕터 요약 (페이지 요약 포함)
    """
    # 챕터 조회
    chapter = db.query(Chapter).filter(
        Chapter.book_id == book_id,
        Chapter.chapter_id == chapter_id
    ).first()
    
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    # 요약 조회
    summary = db.query(Summary).filter(
        Summary.book_id == book_id,
        Summary.chapter_id == chapter.id
    ).first()
    
    if not summary:
        raise HTTPException(status_code=404, detail="Chapter summary not found")
    
    return ChapterSummaryResponse(
        chapter_id=chapter.chapter_id,
        title=chapter.title,
        **summary.summary_data
    )
````

## File: backend/api/schemas/__init__.py
````python
"""
Pydantic 요청/응답 스키마
"""

from .book import (
    BookUploadResponse,
    BookListResponse,
    BookDetailResponse,
    ChapterResponse,
    BookStructureResponse,
)
from .summary import (
    PageSummaryResponse,
    ChapterSummaryResponse,
    BookSummaryResponse,
)
from .search import (
    SearchRequest,
    SearchResultChapter,
    SearchResultPage,
    SearchResultDrilldown,
    SearchResponse,
)

__all__ = [
    # Book 스키마
    "BookUploadResponse",
    "BookListResponse",
    "BookDetailResponse",
    "ChapterResponse",
    "BookStructureResponse",
    # Summary 스키마
    "PageSummaryResponse",
    "ChapterSummaryResponse",
    "BookSummaryResponse",
    # Search 스키마
    "SearchRequest",
    "SearchResultChapter",
    "SearchResultPage",
    "SearchResultDrilldown",
    "SearchResponse",
]
````

## File: backend/api/schemas/book.py
````python
"""
Book 관련 Pydantic 스키마

API 요청/응답에 사용되는 데이터 구조 정의
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from backend.api.models.book import BookStatus


class BookUploadResponse(BaseModel):
    """
    PDF 업로드 응답
    
    POST /api/books/upload의 응답
    """
    id: int
    filename: str
    file_size: int
    status: BookStatus
    uploaded_at: datetime
    
    class Config:
        from_attributes = True  # SQLAlchemy 모델을 Pydantic 모델로 변환 허용


class ChapterResponse(BaseModel):
    """
    챕터 정보 응답
    
    GET /api/books/{id}에 포함되는 챕터 정보
    """
    id: int
    chapter_num: int
    chapter_id: str
    title: str
    start_page: int
    end_page: int
    
    class Config:
        from_attributes = True


class BookDetailResponse(BaseModel):
    """
    책 상세 정보 응답
    
    GET /api/books/{id}의 응답
    """
    id: int
    filename: str
    original_filename: str
    title: Optional[str] = None
    file_size: int
    total_pages: Optional[int] = None
    status: BookStatus
    error_message: Optional[str] = None
    uploaded_at: datetime
    analyzed_at: Optional[datetime] = None
    summarized_at: Optional[datetime] = None
    chapters: List[ChapterResponse] = []
    
    class Config:
        from_attributes = True


class BookListResponse(BaseModel):
    """
    책 목록 응답
    
    GET /api/books의 각 항목
    """
    id: int
    filename: str
    title: Optional[str] = None
    status: BookStatus
    total_pages: Optional[int] = None
    uploaded_at: datetime
    
    class Config:
        from_attributes = True


class BookStructureResponse(BaseModel):
    """
    구조 분석 결과 응답
    
    GET /api/books/{id}/structure의 응답
    """
    intro: List[int] = Field(default_factory=list, description="서문 페이지 번호 목록")
    chapters: List[dict] = Field(default_factory=list, description="챕터 정보 목록")
    notes: List[int] = Field(default_factory=list, description="종문(참고문헌) 페이지 번호 목록")
    
    class Config:
        # structure_data JSON을 직접 파싱
        from_attributes = False
````

## File: backend/api/schemas/search.py
````python
"""
Search 관련 Pydantic 스키마

검색 요청/응답에 사용되는 데이터 구조
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Union


class SearchRequest(BaseModel):
    """
    검색 요청

    POST /api/search의 요청 바디
    """

    query: str = Field(..., min_length=1, max_length=500, description="검색 쿼리")
    mode: Literal["chapter", "page", "drilldown"] = Field(
        default="drilldown",
        description="검색 모드: chapter(챕터만), page(페이지만), drilldown(계층 탐색)",
    )
    k: int = Field(default=5, ge=1, le=20, description="반환할 결과 개수")


# 검색 결과 타입들
class SearchResultChapter(BaseModel):
    """챕터 검색 결과"""

    chapter_id: str
    title: str
    score: float
    summary: str


class SearchResultPage(BaseModel):
    """페이지 검색 결과"""

    page: int
    score: float
    summary: str


class SearchResultDrilldown(BaseModel):
    """Drilldown 검색 결과 (챕터 + 관련 페이지)"""

    chapter: SearchResultChapter
    pages: List[SearchResultPage] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """
    검색 응답

    POST /api/search의 응답
    """

    mode: str = Field(description="사용된 검색 모드")
    results: List[SearchResultDrilldown] = Field(
        default_factory=list, description="검색 결과 목록"
    )
````

## File: backend/api/schemas/summary.py
````python
"""
Summary 관련 Pydantic 스키마

요약 데이터 요청/응답에 사용되는 데이터 구조
"""
from pydantic import BaseModel, Field
from typing import List, Optional


class PageSummaryResponse(BaseModel):
    """
    페이지 요약 응답
    
    ChapterSummaryResponse에 포함되는 페이지별 요약
    """
    page: int
    facts: List[str] = Field(default_factory=list, description="객관적 사실들")
    claims: List[str] = Field(default_factory=list, description="주장/논점들")
    examples: List[str] = Field(default_factory=list, description="예시/사례들")
    keywords: List[str] = Field(default_factory=list, description="핵심 키워드")
    summary: str = Field(default="", description="페이지 요약 텍스트")


class ChapterSummaryResponse(BaseModel):
    """
    챕터 요약 응답
    
    GET /api/books/{id}/chapters/{chapter_id}/summary의 응답
    """
    chapter_id: str
    title: str
    facts: List[str] = Field(default_factory=list, description="챕터 핵심 사실들")
    claims: List[str] = Field(default_factory=list, description="챕터 주요 주장들")
    examples: List[str] = Field(default_factory=list, description="챕터 예시들")
    keywords: List[str] = Field(default_factory=list, description="챕터 키워드")
    summary: str = Field(default="", description="챕터 요약 텍스트")
    page_summaries: List[PageSummaryResponse] = Field(
        default_factory=list,
        description="챕터 내 페이지별 요약 목록"
    )


class BookSummaryResponse(BaseModel):
    """
    책 전체 요약 응답
    
    GET /api/books/{id}/summary의 응답
    """
    book_id: int
    chapters: List[ChapterSummaryResponse] = Field(
        default_factory=list,
        description="챕터별 요약 목록"
    )
````

## File: backend/api/services/__init__.py
````python
"""
비즈니스 로직 서비스 레이어
"""
from .book_service import BookService
from .structure_service import StructureService
from .summary_service import SummaryService
from .search_service import SearchService

__all__ = [
    "BookService",
    "StructureService",
    "SummaryService",
    "SearchService",
]
````

## File: backend/api/services/book_service.py
````python
"""
Book Service

책 파일 및 메타데이터 관리 서비스
"""
from sqlalchemy.orm import Session
from typing import List, Optional
from pathlib import Path

from backend.api.models.book import Book, BookStatus


class BookService:
    """책 관리 서비스"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_book(self, book_id: int) -> Optional[Book]:
        """
        책 조회
        
        Args:
            book_id: 책 ID
            
        Returns:
            Book 또는 None
        """
        return self.db.query(Book).filter(Book.id == book_id).first()
    
    def list_books(self, skip: int = 0, limit: int = 100) -> List[Book]:
        """
        책 목록 조회
        
        Args:
            skip: 건너뛸 항목 수
            limit: 반환할 최대 항목 수
            
        Returns:
            Book 목록
        """
        return self.db.query(Book).order_by(Book.uploaded_at.desc()).offset(skip).limit(limit).all()
    
    def delete_book(self, book_id: int) -> bool:
        """
        책 삭제 (파일 + DB)
        
        Args:
            book_id: 책 ID
            
        Returns:
            성공 여부
        """
        book = self.get_book(book_id)
        if not book:
            return False
        
        # 파일 삭제
        file_path = Path(book.file_path)
        if file_path.exists():
            file_path.unlink()
        
        # DB에서 삭제 (cascade로 chapters, summaries도 자동 삭제됨)
        self.db.delete(book)
        self.db.commit()
        return True
    
    def update_status(
        self,
        book_id: int,
        status: BookStatus,
        error_message: Optional[str] = None
    ):
        """
        책 상태 업데이트
        
        Args:
            book_id: 책 ID
            status: 새로운 상태
            error_message: 에러 메시지 (선택)
        """
        book = self.get_book(book_id)
        if book:
            book.status = status
            if error_message:
                book.error_message = error_message
            self.db.commit()
            self.db.refresh(book)
````

## File: backend/api/services/search_service.py
````python
"""
Search Service

검색 서비스 (기존 Phase 2.4 모듈 래핑)
"""

from sqlalchemy.orm import Session
from typing import List, Optional
import logging
import threading

from backend.api.models.book import Book, Chapter
from backend.search.search_service import SearchService as CoreSearchService

logger = logging.getLogger(__name__)


class SearchService:
    """API 검색 서비스 (기존 검색 모듈 래핑)"""

    # 클래스 변수: 전역 공유 (Singleton 패턴)
    _core_service: Optional[CoreSearchService] = None
    _initialized: bool = False
    _init_lock = threading.Lock()

    def __init__(self, db: Session):
        self.db = db

        # 첫 호출 시에만 Core SearchService 초기화
        if not SearchService._initialized:
            with SearchService._init_lock:
                if not SearchService._initialized:  # Double-checked locking
                    try:
                        logger.info("Initializing Core SearchService...")
                        SearchService._core_service = CoreSearchService()
                        SearchService._core_service.initialize(rebuild_index=False)
                        SearchService._initialized = True
                        logger.info("Vector search initialized successfully")
                    except FileNotFoundError:
                        logger.warning(
                            "Vector index not found. Run POST /api/search/index/build to create index."
                        )
                        SearchService._core_service = None
                    except Exception as e:
                        logger.error(f"Failed to initialize vector search: {e}")
                        SearchService._core_service = None

    def search(self, query: str, mode: str = "drilldown", k: int = 5) -> List[dict]:
        """
        벡터 검색 실행

        Phase 2.4 모듈을 사용하여 계층형 벡터 검색 수행

        Args:
            query: 검색 쿼리
            mode: 검색 모드 (chapter/page/drilldown)
            k: 반환할 결과 개수

        Returns:
            검색 결과 목록
        """
        # Core SearchService 사용 가능 여부 확인
        if SearchService._core_service is None:
            logger.warning("Vector search not available. Returning empty results.")
            return []

        try:
            # Phase 2.4 Core 모듈 호출
            search_result = SearchService._core_service.search(
                query=query, mode=mode, k=k
            )

            # Core SearchService 반환 형식: {"query": "...", "mode": "...", "results": [...], "result_count": 3}
            raw_results = search_result.get("results", [])

            # 결과를 API 스키마 형식으로 변환 (프론트엔드 형식에 맞춤)
            formatted_results = []
            for result in raw_results:
                # drilldown 모드: { chapter: {...}, pages: [...] }
                if mode == "drilldown" and "chapter" in result:
                    chapter_data = result["chapter"]
                    pages_data = result.get("related_pages", [])

                    formatted_results.append(
                        {
                            "chapter": {
                                "chapter_id": chapter_data.get("chapter_id", ""),
                                "title": chapter_data.get("chapter_title", ""),
                                "score": chapter_data.get("score", 0.0),
                                "summary": chapter_data.get("content", ""),
                            },
                            "pages": [
                                {
                                    "page": pg.get("page", 0),
                                    "score": pg.get("score", 0.0),
                                    "summary": pg.get("content", ""),
                                }
                                for pg in pages_data
                            ],
                        }
                    )
                else:
                    # chapter 또는 page 모드: 단일 항목을 { chapter: {...}, pages: [] } 형식으로 래핑
                    if result.get("type") == "page":
                        formatted_results.append(
                            {
                                "chapter": None,
                                "pages": [
                                    {
                                        "page": result.get("page", 0),
                                        "score": result.get("score", 0.0),
                                        "summary": result.get("content", ""),
                                    }
                                ],
                            }
                        )
                    else:  # chapter
                        formatted_results.append(
                            {
                                "chapter": {
                                    "chapter_id": result.get("chapter_id", ""),
                                    "title": result.get("chapter_title", ""),
                                    "score": result.get("score", 0.0),
                                    "summary": result.get("content", ""),
                                },
                                "pages": [],
                            }
                        )

            logger.info(
                f"Search completed: query='{query}', mode={mode}, results={len(formatted_results)}"
            )
            return formatted_results

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {e}", exc_info=True)
            return []

    def search_by_keywords(
        self, query: str, book_id: Optional[int] = None
    ) -> List[dict]:
        """
        키워드 검색 (DB 메타데이터 기반, 벡터 검색 없음)

        Args:
            query: 검색 키워드
            book_id: 특정 책으로 제한 (선택)

        Returns:
            검색 결과 목록
        """
        try:
            # Chapter 테이블에서 제목으로 검색
            query_filter = Chapter.title.ilike(f"%{query}%")

            if book_id:
                chapters = (
                    self.db.query(Chapter)
                    .filter(Chapter.book_id == book_id, query_filter)
                    .all()
                )
            else:
                chapters = self.db.query(Chapter).filter(query_filter).all()

            results = []
            for chapter in chapters:
                results.append(
                    {
                        "chapter_id": chapter.chapter_id,
                        "title": chapter.title,
                        "book_id": chapter.book_id,
                        "start_page": chapter.start_page,
                        "end_page": chapter.end_page,
                    }
                )

            return results

        except Exception as e:
            logger.error(f"Keyword search failed for query '{query}': {e}")
            return []
````

## File: backend/api/services/structure_service.py
````python
"""
Structure Service

책 구조 분석 서비스 (기존 Phase 1 모듈 래핑)
"""
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from backend.api.models.book import Book, Chapter, BookStatus
from backend.parsers.pdf_parser import PDFParser
from backend.structure.structure_builder import StructureBuilder

logger = logging.getLogger(__name__)


class StructureService:
    """구조 분석 서비스"""
    
    def __init__(self, db: Session):
        self.db = db
        self.pdf_parser = PDFParser()
        self.structure_builder = StructureBuilder()
    
    def analyze_book_structure(self, book_id: int):
        """
        책 구조 분석 실행 (백그라운드 작업)
        
        Phase 1 모듈을 사용하여 PDF 파싱 및 구조 분석 수행
        
        Args:
            book_id: 책 ID
        """
        import time
        start_time = time.time()
        
        logger.info(f"[BG START] analyze_book_structure for book_id={book_id}")
        
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            logger.error(f"Book {book_id} not found")
            return
        
        logger.info(f"[BG 0.0s] Book found: {book.filename}")
        
        # 상태 업데이트: ANALYZING
        book.status = BookStatus.ANALYZING
        self.db.commit()
        logger.info(f"[BG {time.time()-start_time:.1f}s] Status updated to ANALYZING")
        
        try:
            logger.info(f"[BG {time.time()-start_time:.1f}s] Starting PDF parsing...")
            
            # Phase 1 모듈 호출: PDF 파싱
            parse_start = time.time()
            parsed_data = self.pdf_parser.parse_pdf(book.file_path)
            parse_time = time.time() - parse_start
            logger.info(f"[BG {time.time()-start_time:.1f}s] PDF parsed in {parse_time:.1f}s: {len(parsed_data.get('pages', []))} pages")
            
            # Phase 1 모듈 호출: 구조 분석
            logger.info(f"[BG {time.time()-start_time:.1f}s] Starting structure building...")
            struct_start = time.time()
            structure = self.structure_builder.build_structure(parsed_data)
            struct_time = time.time() - struct_start
            logger.info(f"[BG {time.time()-start_time:.1f}s] Structure built in {struct_time:.1f}s")
            
            # DB에 결과 저장
            logger.info(f"[BG {time.time()-start_time:.1f}s] Saving to DB...")
            db_start = time.time()
            
            book.structure_data = structure
            book.total_pages = len(parsed_data.get("pages", []))
            book.status = BookStatus.ANALYZED
            book.analyzed_at = datetime.utcnow()
            
            # Chapter 레코드 생성 (실제 구조: structure["main"]["chapters"])
            chapters = structure.get("main", {}).get("chapters", [])
            logger.info(f"[BG {time.time()-start_time:.1f}s] Creating {len(chapters)} chapter records...")
            
            for ch in chapters:
                chapter = Chapter(
                    book_id=book_id,
                    chapter_num=ch.get("number", int(ch["id"].replace("ch", ""))),
                    chapter_id=ch["id"],
                    title=ch["title"],
                    start_page=ch["start_page"],
                    end_page=ch["end_page"]
                )
                self.db.add(chapter)
            
            self.db.commit()
            db_time = time.time() - db_start
            total_time = time.time() - start_time
            
            logger.info(f"[BG {total_time:.1f}s] DB commit in {db_time:.1f}s")
            logger.info(f"[BG COMPLETE] Structure analysis completed for book {book_id} in {total_time:.1f}s")
            
        except Exception as e:
            logger.error(f"Structure analysis failed for book {book_id}: {e}")
            book.status = BookStatus.FAILED
            book.error_message = str(e)
            self.db.commit()
            raise
    
    def get_book_structure(self, book_id: int) -> dict:
        """
        책 구조 조회
        
        Args:
            book_id: 책 ID
            
        Returns:
            구조 데이터 (intro, chapters, notes)
        """
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book or not book.structure_data:
            return None
        
        return book.structure_data
````

## File: backend/api/services/summary_service.py
````python
"""
Summary Service

책 요약 생성 서비스 (기존 Phase 2 모듈 래핑)
메모리 기반 어댑터 패턴 사용
"""

from sqlalchemy.orm import Session
from datetime import datetime
import logging
from typing import Dict, Any, List

from langchain_core.documents import Document

from backend.api.models.book import Book, Chapter, Summary, BookStatus
from backend.summarizers.hierarchical_summarizer import HierarchicalSummarizer
from backend.parsers.pdf_parser import PDFParser

logger = logging.getLogger(__name__)


class SummaryService:
    """요약 생성 서비스 (메모리 기반 어댑터)"""

    def __init__(self, db: Session):
        self.db = db
        self.summarizer = HierarchicalSummarizer()
        self.pdf_parser = PDFParser()

    def _extract_chapter_text(
        self, parsed_data: Dict[str, Any], start_page: int, end_page: int
    ) -> str:
        """
        파싱 데이터에서 챕터 텍스트 추출 (메모리 어댑터)

        DocumentLoader._extract_text_from_pages() 로직을 메모리 버전으로 구현

        Args:
            parsed_data: PDFParser 결과
            start_page: 시작 페이지
            end_page: 종료 페이지

        Returns:
            추출된 텍스트
        """
        texts = []

        # 페이지별 elements 인덱싱
        page_elements = {}
        for page_data in parsed_data.get("pages", []):
            page_num = page_data.get("page_number")
            page_elements[page_num] = page_data.get("elements", [])

        # 챕터 범위의 텍스트 추출
        for page_num in range(start_page, end_page + 1):
            if page_num not in page_elements:
                logger.warning(f"Page {page_num} not found in parsing data")
                continue

            elements = page_elements[page_num]
            for element in elements:
                text = element.get("text", "").strip()
                if text:
                    texts.append(text)

        return "\n".join(texts)

    def _create_chapter_document(
        self, parsed_data: Dict[str, Any], chapter_info: Dict[str, Any]
    ) -> Document:
        """
        챕터 Document 객체 생성 (메모리 어댑터)

        Args:
            parsed_data: PDFParser 결과
            chapter_info: 챕터 정보 (structure["main"]["chapters"]의 항목)

        Returns:
            LangChain Document 객체
        """
        # 챕터 텍스트 추출
        chapter_text = self._extract_chapter_text(
            parsed_data, chapter_info["start_page"], chapter_info["end_page"]
        )

        # Document 생성
        chapter_doc = Document(
            page_content=chapter_text,
            metadata={
                "node_type": "chapter",
                "chapter_id": chapter_info["id"],
                "chapter_number": chapter_info.get(
                    "number", int(chapter_info["id"].replace("ch", ""))
                ),
                "chapter_title": chapter_info["title"],
                "start_page": chapter_info["start_page"],
                "end_page": chapter_info["end_page"],
                "page_count": chapter_info["end_page"] - chapter_info["start_page"] + 1,
            },
        )

        logger.info(
            f"Created Document for {chapter_info['id']}: {len(chapter_text)} chars"
        )
        return chapter_doc

    def summarize_book(self, book_id: int):
        """
        책 요약 생성 실행 (백그라운드 작업)

        메모리 기반 어댑터 패턴:
        1. DB 데이터 조회
        2. PDF 파싱 (캐시 사용)
        3. Document 객체 생성 (메모리)
        4. Phase 2 모듈 호출
        5. 결과를 DB 저장

        Args:
            book_id: 책 ID
        """
        book = self.db.query(Book).filter(Book.id == book_id).first()
        if not book:
            logger.error(f"Book {book_id} not found")
            return

        # 상태 업데이트: SUMMARIZING
        book.status = BookStatus.SUMMARIZING
        self.db.commit()

        try:
            logger.info(
                f"Starting summary generation for book {book_id}: {book.filename}"
            )

            # 구조 데이터 확인
            if not book.structure_data:
                raise ValueError(
                    "Structure data not found. Please analyze structure first."
                )

            # 1. PDF 파싱 (캐시 재사용)
            logger.info(f"Parsing PDF for summary generation...")
            parsed_data = self.pdf_parser.parse_pdf(book.file_path, use_cache=True)

            structure = book.structure_data
            chapters = structure.get("main", {}).get("chapters", [])
            logger.info(f"Summarizing {len(chapters)} chapters")

            # 2. 각 챕터별로 요약 생성
            for ch in chapters:
                chapter = (
                    self.db.query(Chapter)
                    .filter(Chapter.book_id == book_id, Chapter.chapter_id == ch["id"])
                    .first()
                )

                if not chapter:
                    logger.warning(f"Chapter {ch['id']} not found in DB, skipping")
                    continue

                logger.info(f"Summarizing chapter {ch['id']}: {ch['title']}")

                # 3. Document 생성 (메모리 어댑터)
                chapter_doc = self._create_chapter_document(parsed_data, ch)

                # 4. Phase 2 모듈 호출 (올바른 시그니처)
                result = self.summarizer.summarize_chapter(
                    chapter_doc,  # Document 객체
                    use_cache=True,  # 페이지 캐시 사용
                    use_parallel=True,  # 병렬 처리
                    max_concurrent=5,
                )

                # 5. 결과 변환 및 DB 저장
                chapter_summary = result["chapter_summary"]
                summary_data = {
                    # ChapterSummary 필드 (검증됨)
                    "facts": chapter_summary.facts,
                    "claims": chapter_summary.claims,
                    "examples": chapter_summary.examples,
                    "quotes": chapter_summary.quotes,
                    "keywords": chapter_summary.keywords,
                    "summary": chapter_summary.summary,
                    # PageSummary 필드 (실제 존재하는 것만)
                    "page_summaries": [
                        {"page": ps.page, "facts": ps.facts, "summary": ps.summary}
                        for ps in result["page_summaries"]
                    ],
                }

                summary = Summary(
                    book_id=book_id, chapter_id=chapter.id, summary_data=summary_data
                )
                self.db.add(summary)
                logger.info(f"Chapter {ch['id']} summary saved to DB")

            # 상태 업데이트: COMPLETED
            book.status = BookStatus.COMPLETED
            book.summarized_at = datetime.utcnow()
            self.db.commit()

            logger.info(f"Summary generation completed for book {book_id}")

        except Exception as e:
            logger.error(f"Summary generation failed for book {book_id}: {e}")
            book.status = BookStatus.FAILED
            book.error_message = str(e)
            self.db.commit()
            raise

    def get_book_summary(self, book_id: int) -> dict:
        """
        책 전체 요약 조회

        Args:
            book_id: 책 ID

        Returns:
            전체 요약 데이터
        """
        summaries = (
            self.db.query(Summary)
            .filter(Summary.book_id == book_id, Summary.chapter_id.isnot(None))
            .all()
        )

        if not summaries:
            return None

        chapter_summaries = []
        for summary in summaries:
            chapter = (
                self.db.query(Chapter).filter(Chapter.id == summary.chapter_id).first()
            )
            if chapter:
                chapter_summaries.append(
                    {
                        "chapter_id": chapter.chapter_id,
                        "title": chapter.title,
                        **summary.summary_data,
                    }
                )

        return {"book_id": book_id, "chapters": chapter_summaries}

    def get_chapter_summary(self, book_id: int, chapter_id: str) -> dict:
        """
        챕터별 요약 조회

        Args:
            book_id: 책 ID
            chapter_id: 챕터 ID (예: ch1)

        Returns:
            챕터 요약 데이터
        """
        chapter = (
            self.db.query(Chapter)
            .filter(Chapter.book_id == book_id, Chapter.chapter_id == chapter_id)
            .first()
        )

        if not chapter:
            return None

        summary = (
            self.db.query(Summary)
            .filter(Summary.book_id == book_id, Summary.chapter_id == chapter.id)
            .first()
        )

        if not summary:
            return None

        return {
            "chapter_id": chapter.chapter_id,
            "title": chapter.title,
            **summary.summary_data,
        }
````

## File: backend/api/__init__.py
````python
"""
Books Assistant API

FastAPI 백엔드 서버 패키지
"""
````

## File: backend/api/database.py
````python
"""
데이터베이스 연결 및 세션 관리

SQLite 데이터베이스를 사용하여 책, 챕터, 요약 메타데이터 저장
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path

# SQLite 데이터베이스 경로
DB_DIR = Path("cache/database")
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "books.db"

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# SQLite에서는 check_same_thread=False 필수 (FastAPI의 멀티스레드 요청 처리)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # True로 설정하면 SQL 쿼리 로그 출력
)

# 세션 팩토리
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 (모든 ORM 모델의 부모)
Base = declarative_base()


def get_db():
    """
    DB 세션 의존성
    
    FastAPI의 Depends()와 함께 사용:
    @app.get("/api/books")
    def list_books(db: Session = Depends(get_db)):
        ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    데이터베이스 초기화
    
    모든 ORM 모델의 테이블 생성
    FastAPI 앱 시작 시(@app.on_event("startup")) 호출
    """
    # models 패키지의 모든 모델을 import해야 Base.metadata에 등록됨
    from backend.api.models import book  # noqa
    
    Base.metadata.create_all(bind=engine)
````

## File: backend/api/dependencies.py
````python
"""
공통 의존성 (Dependencies)

FastAPI의 Depends()와 함께 사용되는 공통 의존성 함수들
"""
from sqlalchemy.orm import Session
from .database import get_db

# 현재는 database.py의 get_db를 재export
# 향후 인증, 권한, 캐싱 등의 의존성 추가 가능

__all__ = ["get_db"]
````

## File: backend/api/main.py
````python
"""
Books Assistant API

FastAPI 백엔드 서버 메인 앱
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.database import init_db
from backend.api.routers import books, structure, summary, search

# FastAPI 앱 생성
app = FastAPI(
    title="Books Assistant API",
    description="PDF 도서 구조 분석 및 요약 시스템",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 설정 (프론트엔드 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js 개발 서버
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(books.router)
app.include_router(structure.router)
app.include_router(summary.router)
app.include_router(search.router)


@app.on_event("startup")
async def startup_event():
    """앱 시작 시 데이터베이스 초기화"""
    init_db()
    print("Database initialized")
    print("API documentation: http://localhost:8000/docs")


@app.get("/")
async def root():
    """헬스 체크"""
    return {
        "status": "ok",
        "message": "Books Assistant API is running",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """헬스 체크 (상세)"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "endpoints": {
            "books": "/api/books",
            "structure": "/api/books/{id}/analyze",
            "summary": "/api/books/{id}/summarize",
            "search": "/api/search"
        }
    }
````

## File: backend/config/constants.py
````python
"""
Books Assistant - 상수 정의
"""

import re

# 챕터 제목 패턴
CHAPTER_PATTERNS = {
    "korean": re.compile(r"제\s?\d+\s?장"),
    "english": re.compile(r"CHAPTER\s+\d+", re.IGNORECASE),
    "numbered": re.compile(r"^\d+\.\s+\S+"),
    "decimal": re.compile(r"\d+\.\d+"),
    "korean_list": re.compile(r"[가-힣]\.|\(\d+\)"),
}

# 레이아웃 임계값
LAYOUT_THRESHOLDS = {
    "MIN_CHAPTER_PAGES": 3,
    "SCORE_THRESHOLD": 60,
    "FONT_SIZE_WEIGHT": 40,
    "PATTERN_WEIGHT": 30,
    "TOC_WEIGHT": 30,
    "SIMILARITY_THRESHOLD": 0.9,
}

# 목차 탐지 키워드
TOC_KEYWORDS = ["목차", "Contents", "차례", "Table of Contents"]

# 참고문헌 탐지 키워드
REFERENCES_KEYWORDS = ["참고문헌", "References", "Bibliography", "부록", "Appendix"]

# 페이지 분할 설정
PAGE_SPLIT_CONFIG = {
    "MIN_WIDTH_RATIO": 0.3,  # 최소 페이지 비율
    "CENTER_DEVIATION_THRESHOLD": 0.1,  # 중앙선 편차 임계값
}

# 파일 경로 상수
DEFAULT_SAMPLE_PDF = "docs/지능의 탄생.pdf"
OUTPUT_DIRECTORY = "output"
LOGS_DIRECTORY = "logs"
````

## File: backend/config/settings.py
````python
"""
Books Assistant - 설정 관리
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # API 키
    upstage_api_key: str
    openai_api_key: str

    # 로깅 설정
    log_level: str = "INFO"

    # 처리 설정
    batch_size: int = 10
    max_retries: int = 3

    # 파일 경로
    sample_pdf_path: str = "docs/지능의 탄생.pdf"
    output_directory: str = "output"

    # Upstage API 설정
    upstage_api_url: str = "https://api.upstage.ai/v1/document-ai/layout-analyzer"
    upstage_rate_limit: int = 10  # requests per minute

    # OpenAI 설정
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.1

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 전역 설정 인스턴스
settings = Settings()


def create_directories():
    """필요한 디렉토리 생성"""
    directories = [settings.output_directory, "logs", "temp"]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
````

## File: backend/parsers/cache_manager.py
````python
"""
Upstage API 캐싱 시스템 - 비용 절약을 위한 필수 구현
"""
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional, Dict, Any

from backend.config.settings import settings

logger = logging.getLogger(__name__)


class CacheManager:
    """Upstage API 결과 캐싱 매니저"""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir) if cache_dir else Path("cache/upstage")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"CacheManager initialized with cache directory: {self.cache_dir}")

    def get_file_hash(self, pdf_path: str) -> str:
        """PDF 파일의 안전한 해시 생성"""
        try:
            with open(pdf_path, 'rb') as f:
                # 대용량 파일을 위해 청크 단위로 읽기
                hasher = hashlib.md5()
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
                return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Failed to generate hash for {pdf_path}: {e}")
            raise

    def get_cache_key(self, pdf_path: str) -> str:
        """
        PDF 파일 내용 기반 캐시 키 생성
        
        파일 내용 해시만 사용하여 같은 PDF면 경로 무관하게 캐시 재사용
        (Phase 3: API 업로드 시 파일명/경로 변경되어도 캐시 유지)
        """
        try:
            file_hash = self.get_file_hash(pdf_path)
            
            logger.debug(f"Generated cache key: {file_hash} for {pdf_path}")
            return file_hash
            
        except Exception as e:
            logger.error(f"Failed to generate cache key for {pdf_path}: {e}")
            raise

    def get_cache_path(self, cache_key: str) -> Path:
        """캐시 파일 경로 생성"""
        return self.cache_dir / f"{cache_key}.json"

    def is_cache_valid(self, pdf_path: str, cache_key: str) -> bool:
        """
        캐시 유효성 확인
        
        캐시 키가 파일 내용 해시 기반이므로 파일 존재 여부만 확인
        (같은 내용이면 같은 키 → 캐시 재사용)
        """
        cache_file = self.get_cache_path(cache_key)
        return cache_file.exists()

    def get_cached_result(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """캐시된 결과 조회"""
        try:
            cache_key = self.get_cache_key(pdf_path)
            
            if not self.is_cache_valid(pdf_path, cache_key):
                return None
            
            cache_file = self.get_cache_path(cache_key)
            
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
                
            # 캐시 메타데이터 제거
            cached_data.pop("_cache_meta", None)
            
            logger.info(f"Cache hit for {pdf_path}")
            return cached_data
            
        except Exception as e:
            logger.warning(f"Failed to retrieve cache for {pdf_path}: {e}")
            return None

    def save_cache(self, pdf_path: str, result: Dict[str, Any]) -> None:
        """결과를 캐시에 저장"""
        try:
            # Upstage API 응답 검증 (elements 또는 api 필드 존재 확인)
            if not (result.get("elements") is not None or result.get("api")):
                logger.warning(f"Not caching invalid result for {pdf_path}")
                return
            
            cache_key = self.get_cache_key(pdf_path)
            cache_file = self.get_cache_path(cache_key)
            
            # 캐시 메타데이터 추가
            stat = os.stat(pdf_path)
            cache_meta = {
                "file_hash": self.get_file_hash(pdf_path),
                "file_size": stat.st_size,
                "file_mtime": stat.st_mtime,
                "cached_at": time.time(),
                "pdf_path": pdf_path
            }
            
            # 결과 복사본에 메타데이터 추가
            result_to_cache = result.copy()
            result_to_cache["_cache_meta"] = cache_meta
            
            # 임시 파일로 안전하게 저장
            temp_file = cache_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(result_to_cache, f, ensure_ascii=False, indent=2)
            
            # 원자적 이동
            temp_file.replace(cache_file)
            
            logger.info(f"Cached result for {pdf_path} (key: {cache_key})")
            
        except Exception as e:
            logger.error(f"Failed to cache result for {pdf_path}: {e}")

    def invalidate_cache(self, cache_key: str) -> None:
        """특정 캐시 무효화"""
        try:
            cache_file = self.get_cache_path(cache_key)
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"Invalidated cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to invalidate cache {cache_key}: {e}")

    def invalidate_cache_for_file(self, pdf_path: str) -> None:
        """특정 파일의 캐시 무효화"""
        try:
            cache_key = self.get_cache_key(pdf_path)
            self.invalidate_cache(cache_key)
        except Exception as e:
            logger.warning(f"Failed to invalidate cache for {pdf_path}: {e}")

    def cleanup_old_cache(self, max_age_days: int = 30) -> None:
        """오래된 캐시 파일 정리"""
        try:
            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60
            
            cleaned_count = 0
            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    file_age = current_time - cache_file.stat().st_mtime
                    if file_age > max_age_seconds:
                        cache_file.unlink()
                        cleaned_count += 1
                except Exception:
                    continue
                    
            logger.info(f"Cleaned {cleaned_count} old cache files")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old cache: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """캐시 통계 정보"""
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_size = sum(f.stat().st_size for f in cache_files)
            
            return {
                "cache_directory": str(self.cache_dir),
                "total_files": len(cache_files),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {"error": str(e)}
````

## File: backend/parsers/layout_analyzer.py
````python
"""
레이아웃 신호 분석 모듈
"""

import logging
from typing import Dict, List, Any, Tuple, Optional

from backend.config.constants import LAYOUT_THRESHOLDS

logger = logging.getLogger(__name__)


class LayoutAnalyzer:
    """레이아웃 신호 분석 클래스"""

    def __init__(self):
        self.score_weights = {
            "font_size": LAYOUT_THRESHOLDS["FONT_SIZE_WEIGHT"],
            "position": 20,  # 위치 점수
            "spacing": 15,  # 여백 점수
            "category": 15,  # 카테고리 점수
        }

    def analyze_font_signals(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        폰트 크기/굵기 변화 감지

        Args:
            elements: 분석할 요소들

        Returns:
            폰트 신호 분석 결과
        """
        font_sizes = []
        font_weights = []

        for element in elements:
            font_info = element.get("font_info", {})
            size = font_info.get("size", 12)
            weight = font_info.get("weight", "normal")

            font_sizes.append(size)
            font_weights.append(weight)

        if not font_sizes:
            return {
                "max_size": 12,
                "min_size": 12,
                "avg_size": 12,
                "size_variations": [],
            }

        # 통계 계산
        max_size = max(font_sizes)
        min_size = min(font_sizes)
        avg_size = sum(font_sizes) / len(font_sizes)

        # 특이값 찾기 (평균에서 큰 폰트)
        size_variations = []
        for element in elements:
            font_info = element.get("font_info", {})
            size = font_info.get("size", 12)

            if size > avg_size * 1.2:  # 평균보다 20% 이상 큰 폰트
                size_variations.append(
                    {
                        "element": element,
                        "size": size,
                        "ratio": size / avg_size if avg_size > 0 else 1,
                    }
                )

        return {
            "max_size": max_size,
            "min_size": min_size,
            "avg_size": avg_size,
            "size_variations": size_variations,
            "bold_elements": [
                e
                for e in elements
                if e.get("font_info", {}).get("weight") in ["bold", "700"]
            ],
        }

    def calculate_spacing_changes(
        self, elements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        여백(margin) 변화 계산

        Args:
            elements: 분석할 요소들

        Returns:
            여백 변화 정보 리스트
        """
        if len(elements) < 2:
            return []

        # y좌표 기준으로 정렬
        sorted_elements = sorted(elements, key=lambda e: e.get("bbox", {}).get("y0", 0))

        spacing_changes = []

        for i in range(1, len(sorted_elements)):
            prev_element = sorted_elements[i - 1]
            curr_element = sorted_elements[i]

            prev_bbox = prev_element.get("bbox", {})
            curr_bbox = curr_element.get("bbox", {})

            prev_bottom = prev_bbox.get("y1", 0)
            curr_top = curr_bbox.get("y0", 0)

            spacing = curr_top - prev_bottom

            # 큰 여백이 있는 경우 (새 단락이나 섹션 시작 가능성)
            if spacing > 20:  # 임계값은 조정 가능
                spacing_changes.append(
                    {
                        "prev_element": prev_element,
                        "curr_element": curr_element,
                        "spacing": spacing,
                        "is_large_spacing": spacing > 40,
                    }
                )

        return spacing_changes

    def detect_header_footer_patterns(
        self, page_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        헤더/푸터 패턴 인식

        Args:
            page_data: 페이지 데이터

        Returns:
            헤더/푸터 감지 결과
        """
        elements = page_data.get("elements", [])
        page_height = page_data.get("height", 0)

        if not elements or page_height == 0:
            return {"headers": [], "footers": [], "header_zone": 0, "footer_zone": 0}

        # 페이지 상단/하단 10% 영역을 헤더/푸터 영역으로 간주
        header_zone = page_height * 0.1
        footer_zone = page_height * 0.9

        headers = []
        footers = []

        for element in elements:
            bbox = element.get("bbox", {})
            y0 = bbox.get("y0", 0)

            if y0 <= header_zone:
                headers.append(element)
            elif y0 >= footer_zone:
                footers.append(element)

        return {
            "headers": headers,
            "footers": footers,
            "header_zone": header_zone,
            "footer_zone": footer_zone,
            "page_height": page_height,
        }

    def score_layout_signals(
        self, element: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """
        레이아웃 신호 점수화

        Args:
            element: 점수를 계산할 요소
            context: 주변 컨텍스트 (페이지 정보, 다른 요소들 등)

        Returns:
            레이아웃 신호 점수 (0-100)
        """
        total_score = 0.0

        # 1. 폰트 크기 점수
        font_score = self._calculate_font_score(element, context)
        total_score += font_score * (self.score_weights["font_size"] / 100)

        # 2. 위치 점수 (페이지 상단에 가까울수록 높은 점수)
        position_score = self._calculate_position_score(element, context)
        total_score += position_score * (self.score_weights["position"] / 100)

        # 3. 여백 점수 (앞뒤로 큰 여백이 있을수록 높은 점수)
        spacing_score = self._calculate_spacing_score(element, context)
        total_score += spacing_score * (self.score_weights["spacing"] / 100)

        # 4. 카테고리 점수
        category_score = self._calculate_category_score(element)
        total_score += category_score * (self.score_weights["category"] / 100)

        return min(100.0, total_score)

    def _calculate_font_score(
        self, element: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """폰트 크기 기반 점수 계산"""
        font_info = element.get("font_info", {})
        element_size = font_info.get("size", 12)

        avg_size = context.get("avg_font_size", 12)
        if avg_size == 0:
            return 50.0

        # 평균 대비 크기 비율에 따른 점수
        size_ratio = element_size / avg_size

        if size_ratio >= 1.5:  # 평균보다 50% 이상 큰 경우
            return 100.0
        elif size_ratio >= 1.2:  # 평균보다 20% 이상 큰 경우
            return 80.0
        elif size_ratio >= 1.0:
            return 60.0
        else:
            return 30.0

    def _calculate_position_score(
        self, element: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """위치 기반 점수 계산"""
        bbox = element.get("bbox", {})
        y0 = bbox.get("y0", 0)

        page_height = context.get("page_height", 1000)
        if page_height == 0:
            return 50.0

        # 페이지 상단에 가까울수록 높은 점수
        relative_y = y0 / page_height

        if relative_y <= 0.1:  # 상단 10% 영역
            return 100.0
        elif relative_y <= 0.2:  # 상단 20% 영역
            return 80.0
        elif relative_y <= 0.3:  # 상단 30% 영역
            return 60.0
        else:
            return 40.0

    def _calculate_spacing_score(
        self, element: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """여백 기반 점수 계산"""
        # 주변 요소들과의 간격 분석은 별도 구현 필요
        # 현재는 간단한 구현
        return 50.0

    def _calculate_category_score(self, element: Dict[str, Any]) -> float:
        """카테고리 기반 점수 계산"""
        category = element.get("category", "paragraph")

        category_scores = {
            "heading": 100.0,
            "title": 100.0,
            "subtitle": 80.0,
            "paragraph": 30.0,
            "table": 40.0,
            "list_item": 50.0,
        }

        return category_scores.get(category, 50.0)

    def analyze_page_layout(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        페이지 전체 레이아웃 분석

        Args:
            page_data: 페이지 데이터

        Returns:
            레이아웃 분석 결과
        """
        elements = page_data.get("elements", [])

        # 1. 폰트 신호 분석
        font_analysis = self.analyze_font_signals(elements)

        # 2. 여백 변화 분석
        spacing_changes = self.calculate_spacing_changes(elements)

        # 3. 헤더/푸터 감지
        header_footer = self.detect_header_footer_patterns(page_data)

        # 4. 각 요소별 레이아웃 점수 계산
        context = {
            "avg_font_size": font_analysis.get("avg_size", 12),
            "page_height": page_data.get("height", 1000),
        }

        scored_elements = []
        for element in elements:
            score = self.score_layout_signals(element, context)
            scored_elements.append(
                {
                    "element": element,
                    "layout_score": score,
                    "is_heading_candidate": score
                    >= LAYOUT_THRESHOLDS["SCORE_THRESHOLD"],
                }
            )

        return {
            "page_number": page_data.get("page_number"),
            "font_analysis": font_analysis,
            "spacing_changes": spacing_changes,
            "header_footer": header_footer,
            "scored_elements": scored_elements,
            "layout_summary": {
                "total_elements": len(elements),
                "heading_candidates": len(
                    [se for se in scored_elements if se["is_heading_candidate"]]
                ),
                "large_spacings": len(
                    [sc for sc in spacing_changes if sc["is_large_spacing"]]
                ),
                "has_headers": len(header_footer["headers"]) > 0,
                "has_footers": len(header_footer["footers"]) > 0,
            },
        }
````

## File: backend/parsers/page_splitter.py
````python
"""
양면 스캔 페이지 분리 로직
"""

import logging
from typing import Dict, List, Any, Tuple, Optional

from backend.config.constants import PAGE_SPLIT_CONFIG

logger = logging.getLogger(__name__)


class PageSplitter:
    """양면 스캔 페이지 분리 처리 클래스"""

    def __init__(self, min_width_ratio: float = None, center_threshold: float = None):
        self.min_width_ratio = min_width_ratio or PAGE_SPLIT_CONFIG["MIN_WIDTH_RATIO"]
        self.center_threshold = (
            center_threshold or PAGE_SPLIT_CONFIG["CENTER_DEVIATION_THRESHOLD"]
        )

    def detect_double_page_layout(self, page_data: Dict[str, Any]) -> bool:
        """
        양면 스캔 레이아웃 감지

        Args:
            page_data: 페이지 데이터 (elements 포함)

        Returns:
            양면 스캔 여부
        """
        elements = page_data.get("elements", [])
        if not elements:
            return False

        page_width = page_data.get("width", 0)
        if page_width == 0:
            return False

        # 중심선 근처에서 요소들의 분포 분석
        center_x = page_width / 2
        left_elements = 0
        right_elements = 0

        for element in elements:
            bbox = element.get("bbox", {})
            x0 = bbox.get("x0", 0)
            x1 = bbox.get("x1", 0)
            element_center = (x0 + x1) / 2

            # 요소 중심이 페이지 중심선의 어느 쪽에 있는지 판단
            if element_center < center_x - (page_width * 0.1):
                left_elements += 1
            elif element_center > center_x + (page_width * 0.1):
                right_elements += 1

        # 양쪽에 충분한 요소가 있으면 양면 스캔으로 판단
        total_elements = len(elements)
        min_elements_per_side = max(2, total_elements * 0.1)

        return (
            left_elements >= min_elements_per_side
            and right_elements >= min_elements_per_side
        )

    def calculate_centerline(self, page_data: Dict[str, Any]) -> float:
        """
        동적 중앙선 계산 알고리즘

        Args:
            page_data: 페이지 데이터

        Returns:
            계산된 중앙선 x 좌표
        """
        elements = page_data.get("elements", [])
        if not elements:
            return page_data.get("width", 0) / 2

        page_width = page_data.get("width", 0)

        # 텍스트 요소들의 중심점을 기준으로 중앙선 계산
        text_elements = [elem for elem in elements if elem.get("text", "").strip()]

        if not text_elements:
            return page_width / 2

        # 각 요소의 중심점들
        center_points = []
        for element in text_elements:
            bbox = element.get("bbox", {})
            x0 = bbox.get("x0", 0)
            x1 = bbox.get("x1", 0)
            if x0 < x1:  # 유효한 bbox
                center_points.append((x0 + x1) / 2)

        if not center_points:
            return page_width / 2

        # 중심점들을 정렬하고 중간값 사용
        center_points.sort()

        # 양쪽 페이지의 경계를 찾기 위해 중심점 분포 분석
        if len(center_points) >= 4:
            # 4분위수로 나누어 중간 영역 찾기
            q1 = center_points[len(center_points) // 4]
            q3 = center_points[3 * len(center_points) // 4]

            # 중간 영역의 평균을 중앙선으로 사용
            middle_points = [p for p in center_points if q1 <= p <= q3]
            if middle_points:
                return sum(middle_points) / len(middle_points)

        # 단순히 전체 중심점의 중간값 사용
        return center_points[len(center_points) // 2]

    def split_double_page(
        self, page_data: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        양면 스캔 페이지를 좌우로 분리

        Args:
            page_data: 원본 페이지 데이터

        Returns:
            (왼쪽 페이지, 오른쪽 페이지) 튜플
        """
        elements = page_data.get("elements", [])
        page_width = page_data.get("width", 0)
        page_height = page_data.get("height", 0)
        page_number = page_data.get("page_number", 1)

        # 중앙선 계산
        center_x = self.calculate_centerline(page_data)

        # 요소들을 좌우로 분류
        left_elements = []
        right_elements = []

        for element in elements:
            bbox = element.get("bbox", {})
            x0 = bbox.get("x0", 0)
            x1 = bbox.get("x1", 0)
            element_center = (x0 + x1) / 2

            # 요소 중심이 중앙선보다 왼쪽에 있으면 왼쪽 페이지
            if element_center < center_x:
                # bbox를 좌측 페이지 기준으로 조정
                adjusted_element = self._adjust_element_position(element, offset_x=0)
                left_elements.append(adjusted_element)
            else:
                # 오른쪽 페이지로 이동하면서 x 좌표 조정
                adjusted_element = self._adjust_element_position(
                    element, offset_x=-center_x, new_width=page_width - center_x
                )
                right_elements.append(adjusted_element)

        # 좌우 페이지 생성
        left_page = {
            "page_number": f"{page_number}L",
            "width": center_x,
            "height": page_height,
            "elements": left_elements,
            "metadata": {
                "split_from": page_number,
                "side": "left",
                "original_width": page_width,
            },
        }

        right_page = {
            "page_number": f"{page_number}R",
            "width": page_width - center_x,
            "height": page_height,
            "elements": right_elements,
            "metadata": {
                "split_from": page_number,
                "side": "right",
                "original_width": page_width,
                "center_x": center_x,
            },
        }

        return left_page, right_page

    def _adjust_element_position(
        self, element: Dict[str, Any], offset_x: float = 0, new_width: float = None
    ) -> Dict[str, Any]:
        """요소의 위치를 조정하여 새 페이지에서 올바른 좌표 사용"""
        adjusted_element = element.copy()

        bbox = element.get("bbox", {}).copy()
        x0 = bbox.get("x0", 0)
        x1 = bbox.get("x1", 0)

        # x 좌표 조정
        new_x0 = max(0, x0 + offset_x)
        new_x1 = max(new_x0, x1 + offset_x)

        # 새 페이지 너비에 맞게 조정
        if new_width is not None:
            new_x1 = min(new_x1, new_width)

        adjusted_bbox = {**bbox, "x0": new_x0, "x1": new_x1}

        adjusted_element["bbox"] = adjusted_bbox
        return adjusted_element

    def process_pdf_pages(self, parsed_pdf: Dict[str, Any], force_split: bool = False) -> Dict[str, Any]:
        """
        PDF 전체 페이지에 대해 양면 스캔 분리 처리

        Args:
            parsed_pdf: Upstage API로 파싱된 PDF 결과
            force_split: 강제 분리 적용 여부

        Returns:
            분리 처리된 PDF 결과
        """
        if not parsed_pdf.get("success"):
            logger.warning("PDF parsing was not successful, skipping page splitting")
            return parsed_pdf

        pages = parsed_pdf.get("pages", [])
        processed_pages = []

        logger.info(f"Processing {len(pages)} pages for double-page detection (force_split={force_split})")

        for page in pages:
            should_split = force_split or self.detect_double_page_layout(page)
            
            if should_split:
                if force_split:
                    logger.info(f"Force splitting page {page.get('page_number')}")
                else:
                    logger.info(f"Splitting double page {page.get('page_number')}")
                
                left_page, right_page = self.split_double_page(page)
                processed_pages.extend([left_page, right_page])
            else:
                processed_pages.append(page)

        # 페이지 순서 재정렬 (좌 → 우)
        processed_pages = self._reorder_pages(processed_pages)

        # 결과 업데이트
        result = parsed_pdf.copy()
        result.update(
            {
                "pages": processed_pages,
                "total_pages": len(processed_pages),
                "original_pages": len(pages),
                "split_applied": len(processed_pages) > len(pages),
                "force_split_applied": force_split,  # 강제 분리 적용 여부 추가
            }
        )

        logger.info(
            f"Page splitting completed: {len(pages)} → {len(processed_pages)} pages (force_split={force_split})"
        )
        return result

    def _reorder_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """분리된 페이지들을 올바른 순서로 재정렬 (좌 → 우)"""
        # 페이지 번호별로 그룹화
        page_groups = {}

        for page in pages:
            page_num = page.get("page_number", 1)
            side = page.get("metadata", {}).get("side", "single")

            if isinstance(page_num, str) and "L" in page_num:
                # 분리된 페이지인 경우
                base_num = int(page_num.rstrip("L"))
                if base_num not in page_groups:
                    page_groups[base_num] = {}
                page_groups[base_num]["left"] = page
            elif isinstance(page_num, str) and "R" in page_num:
                # 분리된 페이지인 경우
                base_num = int(page_num.rstrip("R"))
                if base_num not in page_groups:
                    page_groups[base_num] = {}
                page_groups[base_num]["right"] = page
            else:
                # 단일 페이지인 경우
                page_groups[page_num] = {"single": page}

        # 순서대로 정렬하여 재구성
        ordered_pages = []
        for page_num in sorted(page_groups.keys()):
            group = page_groups[page_num]

            if "single" in group:
                # 단일 페이지
                ordered_pages.append(group["single"])
            else:
                # 분리된 페이지 - 좌 → 우 순서
                if "left" in group:
                    ordered_pages.append(group["left"])
                if "right" in group:
                    ordered_pages.append(group["right"])

        return ordered_pages
````

## File: backend/parsers/pdf_parser.py
````python
"""
PDF 파싱 메인 모듈

Upstage API를 직접 호출하여 PDF를 파싱하고,
양면 스캔 분리 처리를 수행합니다.
"""

import os
import logging
from typing import Dict, Any, List
from pathlib import Path
from bs4 import BeautifulSoup
import re

from backend.config.settings import settings
from backend.parsers.upstage_api_client import UpstageAPIClient
from backend.parsers.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class PDFParser:
    """
    PDF 파싱 메인 클래스

    Flow:
    1. 캐시 확인
    2. 캐시 미스 시 Upstage API 호출 및 캐싱
    3. API 응답 → 구조화된 Elements 변환
    4. 양면 분리 로직 적용
    5. 최종 JSON 반환
    """

    def __init__(self, enable_cache: bool = True, clean_output: bool = True):
        """
        Args:
            enable_cache: 캐시 사용 여부
            clean_output: 출력 시 불필요한 필드 제거 (original_page, page)
        """
        self.upstage_client = UpstageAPIClient(settings.upstage_api_key)
        self.cache_manager = CacheManager() if enable_cache else None
        self.clean_output = clean_output

    def parse_pdf(
        self, pdf_path: str, use_cache: bool = True, force_split: bool = False
    ) -> Dict[str, Any]:
        """
        PDF 파싱 메인 함수

        Args:
            pdf_path: PDF 파일 경로
            use_cache: 캐시 사용 여부
            force_split: 강제 양면 분리 여부

        Returns:
            {
                "success": True,
                "pages": [
                    {
                        "page_number": 1,
                        "original_page": 1,
                        "side": "left",
                        "elements": [
                            {
                                "id": 0,
                                "page": 1,
                                "text": "...",
                                "category": "paragraph",
                                "font_size": 20,
                                "bbox": {"x0": 0.1, "y0": 0.2, ...}
                            },
                            ...
                        ]
                    },
                    ...
                ],
                "total_pages": 4,
                "original_pages": 2,
                "split_applied": True,
                "metadata": {...}
            }
        """
        try:
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                raise FileNotFoundError(f"PDF not found: {pdf_path}")

            logger.info(f"🔍 Parsing PDF: {pdf_path.name}")

            # 1. 캐시 확인
            api_response = None
            if use_cache and self.cache_manager:
                api_response = self.cache_manager.get_cached_result(str(pdf_path))
                if api_response:
                    logger.info(f"💾 Using cached API response for {pdf_path.name}")

            # 2. API 호출
            if api_response is None:
                api_response = self.upstage_client.parse_pdf(str(pdf_path))

                # 캐싱 (API 응답 원본 그대로)
                if use_cache and self.cache_manager:
                    self.cache_manager.save_cache(str(pdf_path), api_response)
                    logger.info(f"💾 Cached API response for {pdf_path.name}")

            # 3. Elements 구조화
            logger.info("🔧 Structuring elements...")
            structured_elements = self._structure_elements(api_response)

            # 4. 양면 분리
            logger.info("📄 Splitting pages by side...")
            pages = self._split_pages_by_side(structured_elements, force_split)

            # 5. clean_output 처리 (불필요한 필드 제거)
            if self.clean_output:
                pages = self._clean_pages(pages)
            
            # 6. 최종 결과
            original_pages = api_response.get("usage", {}).get("pages", 0)
            result = {
                "success": True,
                "pages": pages,
                "total_pages": len(pages),
                "original_pages": original_pages,
                "split_applied": len(pages) > original_pages,
                "force_split_applied": force_split,
                "pdf_path": str(pdf_path),
                "metadata": {
                    "api_version": api_response.get("api"),
                    "model": api_response.get("model"),
                    "processing_applied": {
                        "upstage_parsing": True,
                        "element_structuring": True,
                        "page_splitting": len(pages) > original_pages,
                    },
                },
            }

            logger.info(
                f"✅ Parsing completed: {original_pages} original pages → {len(pages)} final pages"
            )
            return result

        except Exception as e:
            logger.error(f"❌ PDF parsing failed: {e}")
            raise

    def _structure_elements(self, api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        API 응답의 elements를 우리 형식으로 구조화

        Input: api_response["elements"] = [
            {
                "id": 0,
                "page": 1,
                "category": "paragraph",
                "coordinates": [{"x": 0.1, "y": 0.2}, ...],
                "content": {"html": "<p>...</p>", ...}
            },
            ...
        ]

        Output: [
            {
                "id": 0,
                "page": 1,
                "text": "텍스트 내용",
                "category": "paragraph",
                "font_size": 20,
                "bbox": {"x0": 0.1, "y0": 0.2, "x1": 0.5, "y1": 0.3, "width": 0.4, "height": 0.1}
            },
            ...
        ]
        """
        elements = api_response.get("elements", [])
        structured = []

        for elem in elements:
            # HTML에서 텍스트 추출
            html_content = elem.get("content", {}).get("html", "")
            text = self._extract_text_from_html(html_content)

            # Font size 추출
            font_size = self._extract_font_size(html_content)

            # Bbox 계산
            bbox = self._calculate_bbox(elem.get("coordinates", []))

            structured.append(
                {
                    "id": elem.get("id"),
                    "page": elem.get("page"),  # 내부 처리용 (양면 분리에 필요)
                    "text": text,
                    "category": elem.get("category", "unknown"),
                    "font_size": font_size,
                    "bbox": bbox,
                }
            )

        logger.info(f"Structured {len(structured)} elements")
        return structured

    def _extract_text_from_html(self, html: str) -> str:
        """HTML에서 순수 텍스트 추출"""
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(strip=True)

    def _extract_font_size(self, html: str) -> int:
        """HTML style에서 font-size 추출"""
        if not html:
            return 12
        match = re.search(r"font-size:(\d+)px", html)
        return int(match.group(1)) if match else 12

    def _calculate_bbox(self, coordinates: List[Dict]) -> Dict[str, float]:
        """좌표 배열에서 bbox 계산"""
        if not coordinates:
            return {"x0": 0, "y0": 0, "x1": 0, "y1": 0, "width": 0, "height": 0}

        x_coords = [c["x"] for c in coordinates]
        y_coords = [c["y"] for c in coordinates]

        x0, x1 = min(x_coords), max(x_coords)
        y0, y1 = min(y_coords), max(y_coords)

        return {
            "x0": x0,
            "y0": y0,
            "x1": x1,
            "y1": y1,
            "width": x1 - x0,
            "height": y1 - y0,
        }

    def _split_pages_by_side(
        self, elements: List[Dict[str, Any]], force_split: bool
    ) -> List[Dict[str, Any]]:
        """
        페이지별 양면 분리 (상대좌표 기준 0.5 고정)

        좌표가 정규화된 상대좌표이므로:
        - x < 0.5: 좌측 페이지
        - x >= 0.5: 우측 페이지
        """
        CENTERLINE = 0.5  # 고정 중앙선

        # 페이지별로 그룹화
        pages_dict = {}
        for elem in elements:
            page_num = elem["page"]
            if page_num not in pages_dict:
                pages_dict[page_num] = []
            pages_dict[page_num].append(elem)

        # 페이지별로 좌/우 분리
        result_pages = []
        page_counter = 1

        for original_page in sorted(pages_dict.keys()):
            page_elements = pages_dict[original_page]

            # 좌/우 분리 (고정 중앙선 0.5 기준)
            left_elements = [e for e in page_elements if e["bbox"]["x0"] < CENTERLINE]
            right_elements = [e for e in page_elements if e["bbox"]["x0"] >= CENTERLINE]

            logger.debug(
                f"  Page {original_page}: {len(page_elements)} elements → "
                f"{len(left_elements)} left, {len(right_elements)} right "
                f"(centerline={CENTERLINE})"
            )

            # 좌측 페이지 (요소가 있을 경우만)
            if left_elements:
                result_pages.append(
                    {
                        "page_number": page_counter,
                        "original_page": original_page,
                        "side": "left",
                        "elements": sorted(
                            left_elements,
                            key=lambda x: (x["bbox"]["y0"], x["bbox"]["x0"]),
                        ),
                        "metadata": {
                            "is_split": True,
                            "centerline": CENTERLINE,
                            "element_count": len(left_elements),
                        },
                    }
                )
                page_counter += 1

            # 우측 페이지 (요소가 있을 경우만)
            if right_elements:
                result_pages.append(
                    {
                        "page_number": page_counter,
                        "original_page": original_page,
                        "side": "right",
                        "elements": sorted(
                            right_elements,
                            key=lambda x: (x["bbox"]["y0"], x["bbox"]["x0"]),
                        ),
                        "metadata": {
                            "is_split": True,
                            "centerline": CENTERLINE,
                            "element_count": len(right_elements),
                        },
                    }
                )
                page_counter += 1

        logger.info(f"Page splitting completed: {len(pages_dict)} original pages → {len(result_pages)} split pages")
        return result_pages

    def _clean_pages(self, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        불필요한 필드 제거 (clean_output=True일 때)
        
        제거할 필드:
        - 페이지 레벨: original_page
        - element 레벨: page
        """
        import copy
        cleaned_pages = copy.deepcopy(pages)
        
        for page in cleaned_pages:
            # original_page 제거
            if "original_page" in page:
                del page["original_page"]
            
            # elements 내의 page 필드 제거
            if "elements" in page:
                for element in page["elements"]:
                    if "page" in element:
                        del element["page"]
        
        return cleaned_pages
````

## File: backend/parsers/text_processor.py
````python
"""
텍스트 정렬 및 정제 처리 모듈
"""

import logging
import re
from typing import Dict, List, Any, Tuple

logger = logging.getLogger(__name__)


class TextProcessor:
    """텍스트 정렬 및 정제 처리 클래스"""

    def __init__(self):
        # 특수문자 정제 패턴
        self.cleanup_patterns = [
            (r"\s+", " "),  # 여러 공백을 하나로
            (r"^\s+|\s+$", ""),  # 앞뒤 공백 제거
            (r"[^\w\s가-힣.,!?;:()[\]]", ""),  # 기본 문장부호만 유지
        ]

    def sort_elements_by_position(
        self, elements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        요소들을 (y0, x0) 좌표 기준으로 정렬

        Args:
            elements: 정렬할 요소들 리스트

        Returns:
            정렬된 요소들 리스트 (위에서 아래로, 왼쪽에서 오른쪽으로)
        """

        def sort_key(element):
            bbox = element.get("bbox", {})
            y0 = bbox.get("y0", 0)
            x0 = bbox.get("x0", 0)
            return (y0, x0)  # 먼저 y좌표, 그 다음 x좌표로 정렬

        return sorted(elements, key=sort_key)

    def merge_paragraph_elements(
        self, elements: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        인접한 단락 요소들 병합

        Args:
            elements: 병합할 요소들 리스트

        Returns:
            병합된 요소들 리스트
        """
        if not elements:
            return elements

        sorted_elements = self.sort_elements_by_position(elements)
        merged_elements = []
        current_paragraph = None

        for element in sorted_elements:
            category = element.get("category", "paragraph")
            text = element.get("text", "").strip()

            if not text:  # 빈 텍스트 요소는 건너뛰기
                continue

            # 단락 요소인 경우 병합 로직 적용
            if category == "paragraph" and current_paragraph is not None:
                # 현재 단락과 병합 가능한지 확인
                if self._can_merge_elements(current_paragraph, element):
                    current_paragraph = self._merge_two_elements(
                        current_paragraph, element
                    )
                    continue

            # 이전 단락이 있으면 결과에 추가
            if current_paragraph is not None:
                merged_elements.append(current_paragraph)

            # 새 단락 시작
            current_paragraph = element.copy()

        # 마지막 단락 추가
        if current_paragraph is not None:
            merged_elements.append(current_paragraph)

        return merged_elements

    def _can_merge_elements(self, elem1: Dict[str, Any], elem2: Dict[str, Any]) -> bool:
        """두 요소가 병합 가능한지 판단"""
        bbox1 = elem1.get("bbox", {})
        bbox2 = elem2.get("bbox", {})

        # y 좌표 차이가 작은지 확인 (같은 줄 또는 인접한 줄)
        y1_bottom = bbox1.get("y1", 0)
        y2_top = bbox2.get("y0", 0)
        y_distance = abs(y2_top - y1_bottom)

        # 폰트 정보가 유사한지 확인
        font1 = elem1.get("font_info", {})
        font2 = elem2.get("font_info", {})

        font_size_diff = abs(font1.get("size", 12) - font2.get("size", 12))

        # 병합 조건: y거리가 작고, 폰트 크기가 유사함
        return y_distance < 50 and font_size_diff < 3

    def _merge_two_elements(
        self, elem1: Dict[str, Any], elem2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """두 요소를 하나로 병합"""
        text1 = elem1.get("text", "").strip()
        text2 = elem2.get("text", "").strip()

        # 텍스트 합치기 (줄바꿈 또는 공백으로)
        if text1 and text2:
            # 두 요소 간의 거리에 따라 구분자 결정
            bbox1 = elem1.get("bbox", {})
            bbox2 = elem2.get("bbox", {})

            y1_bottom = bbox1.get("y1", 0)
            y2_top = bbox2.get("y0", 0)

            if y2_top - y1_bottom > 10:  # 세로 거리가 있으면 줄바꿈
                merged_text = f"{text1}\n{text2}"
            else:  # 같은 줄이면 공백
                merged_text = f"{text1} {text2}"
        else:
            merged_text = text1 + text2

        # bbox 업데이트 (두 요소를 포함하는 영역)
        bbox1 = elem1.get("bbox", {})
        bbox2 = elem2.get("bbox", {})

        merged_bbox = {
            "x0": min(bbox1.get("x0", 0), bbox2.get("x0", 0)),
            "y0": min(bbox1.get("y0", 0), bbox2.get("y0", 0)),
            "x1": max(bbox1.get("x1", 0), bbox2.get("x1", 0)),
            "y1": max(bbox1.get("y1", 0), bbox2.get("y1", 0)),
        }

        return {
            "text": merged_text,
            "category": elem1.get("category", "paragraph"),
            "bbox": merged_bbox,
            "font_info": elem1.get("font_info", {}),
            "confidence": min(
                elem1.get("confidence", 1.0), elem2.get("confidence", 1.0)
            ),
        }

    def clean_text(self, text: str, aggressive: bool = False) -> str:
        """
        텍스트 정제 (특수문자, 공백 등 처리)

        Args:
            text: 정제할 텍스트
            aggressive: 강력한 정제 모드 (기본 문장부호만 유지)

        Returns:
            정제된 텍스트
        """
        if not text:
            return ""

        cleaned_text = text

        # 공백 정리
        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

        if aggressive:
            # 강력한 정제: 기본 문자와 문장부호만 유지
            cleaned_text = re.sub(r"[^\w\s가-힣.,!?;:()[\]]", "", cleaned_text)

        return cleaned_text

    def process_page_elements(self, page_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        페이지의 모든 요소들을 정렬 및 정제 처리

        Args:
            page_data: 페이지 데이터

        Returns:
            처리된 페이지 데이터
        """
        elements = page_data.get("elements", [])

        # 텍스트 정제
        cleaned_elements = []
        for element in elements:
            text = element.get("text", "")
            if text:
                cleaned_text = self.clean_text(text)
                if cleaned_text:  # 정제 후에도 텍스트가 남아있으면
                    element_copy = element.copy()
                    element_copy["text"] = cleaned_text
                    cleaned_elements.append(element_copy)
            else:
                cleaned_elements.append(element)

        # 위치 기준 정렬
        sorted_elements = self.sort_elements_by_position(cleaned_elements)

        # 단락 병합
        merged_elements = self.merge_paragraph_elements(sorted_elements)

        # 결과 페이지 생성
        processed_page = page_data.copy()
        processed_page["elements"] = merged_elements

        # 메타데이터 업데이트
        metadata = processed_page.get("metadata", {})
        metadata.update(
            {
                "original_element_count": len(elements),
                "processed_element_count": len(merged_elements),
                "text_processing_applied": True,
            }
        )
        processed_page["metadata"] = metadata

        return processed_page

    def generate_final_structure(self, processed_pdf: Dict[str, Any]) -> Dict[str, Any]:
        """
        최종 JSON 구조 생성

        Args:
            processed_pdf: 처리된 PDF 데이터

        Returns:
            최종 구조화된 데이터
        """
        pages = processed_pdf.get("pages", [])

        # 전체 통계 계산
        total_elements = 0
        category_stats = {}

        for page in pages:
            elements = page.get("elements", [])
            total_elements += len(elements)

            for element in elements:
                category = element.get("category", "unknown")
                category_stats[category] = category_stats.get(category, 0) + 1

        # 최종 구조
        final_structure = {
            "pdf_info": {
                "path": processed_pdf.get("pdf_path"),
                "total_pages": len(pages),
                "total_elements": total_elements,
                "category_distribution": category_stats,
            },
            "pages": pages,
            "processing_summary": {
                "split_applied": processed_pdf.get("split_applied", False),
                "original_pages": processed_pdf.get("original_pages", len(pages)),
                "text_processing_applied": True,
            },
            "metadata": processed_pdf.get("metadata", {}),
        }

        return final_structure
````

## File: backend/parsers/upstage_api_client.py
````python
"""
Upstage API 직접 호출 클라이언트

Python requests를 사용하여 Upstage Document Parse API를 직접 호출합니다.
100페이지 초과 시 자동으로 분할 파싱합니다.
"""

import requests
from typing import Dict, Any, List
from pathlib import Path
import logging
import time
from PyPDF2 import PdfReader, PdfWriter
import tempfile

logger = logging.getLogger(__name__)


class UpstageAPIClient:
    """Upstage Document Parse API 클라이언트"""

    MAX_PAGES_PER_REQUEST = 100  # API 페이지 제한

    def __init__(self, api_key: str):
        """
        Args:
            api_key: Upstage API 키
        """
        self.api_key = api_key
        self.url = "https://api.upstage.ai/v1/document-digitization"

    def parse_pdf(self, pdf_path: str, retries: int = 3) -> Dict[str, Any]:
        """
        PDF 파싱 (100페이지 초과 시 자동 분할)

        Args:
            pdf_path: PDF 파일 경로
            retries: 재시도 횟수

        Returns:
            {
                "api": "2.0",
                "model": "document-parse-250618",
                "usage": {"pages": total_pages},
                "content": {"html": "...", "markdown": "", "text": ""},
                "elements": [...],
                "metadata": {
                    "split_parsing": True/False,
                    "total_chunks": N
                }
            }
        """
        # PDF 페이지 수 확인
        total_pages = self._get_pdf_page_count(pdf_path)
        logger.info(f"📄 PDF has {total_pages} pages")

        if total_pages <= self.MAX_PAGES_PER_REQUEST:
            # 100페이지 이하: 한 번에 파싱
            logger.info(f"📡 Single request parsing ({total_pages} pages)")
            result = self._parse_single_pdf(pdf_path, retries)
            result["metadata"] = {"split_parsing": False, "total_chunks": 1}
            return result
        else:
            # 100페이지 초과: 분할 파싱
            logger.info(
                f"📡 Split parsing required ({total_pages} pages, "
                f"max {self.MAX_PAGES_PER_REQUEST} per request)"
            )
            return self._parse_pdf_in_chunks(pdf_path, total_pages, retries)

    def _get_pdf_page_count(self, pdf_path: str) -> int:
        """PDF 페이지 수 확인"""
        try:
            reader = PdfReader(pdf_path)
            return len(reader.pages)
        except Exception as e:
            logger.error(f"Failed to read PDF page count: {e}")
            # 페이지 수를 알 수 없으면 일단 단일 파싱 시도
            return 0

    def _split_pdf(
        self, pdf_path: str, start_page: int, end_page: int, output_path: str
    ) -> None:
        """PDF를 특정 페이지 범위로 분할"""
        reader = PdfReader(pdf_path)
        writer = PdfWriter()

        for page_num in range(start_page, min(end_page, len(reader.pages))):
            writer.add_page(reader.pages[page_num])

        with open(output_path, "wb") as output_file:
            writer.write(output_file)

    def _parse_pdf_in_chunks(
        self, pdf_path: str, total_pages: int, retries: int
    ) -> Dict[str, Any]:
        """
        PDF를 100페이지씩 분할하여 파싱

        각 청크를 별도로 파싱한 후 결과를 병합합니다.
        """
        all_elements = []
        chunk_count = 0
        page_offset = 0

        # 100페이지씩 분할
        for start_page in range(0, total_pages, self.MAX_PAGES_PER_REQUEST):
            end_page = min(start_page + self.MAX_PAGES_PER_REQUEST, total_pages)
            chunk_count += 1

            logger.info(
                f"📄 Processing chunk {chunk_count}: "
                f"pages {start_page + 1}-{end_page} of {total_pages}"
            )

            # 임시 파일로 PDF 분할
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
                temp_path = temp_file.name

            try:
                self._split_pdf(pdf_path, start_page, end_page, temp_path)

                # 분할된 PDF 파싱
                chunk_result = self._parse_single_pdf(temp_path, retries)

                # elements 수집 및 page 번호 조정
                for elem in chunk_result.get("elements", []):
                    # 원본 PDF의 페이지 번호로 조정
                    elem["page"] = elem["page"] + page_offset
                    # ID 재조정 (중복 방지)
                    elem["id"] = len(all_elements)
                    all_elements.append(elem)

                page_offset += chunk_result.get("usage", {}).get("pages", 0)

                # Rate limit 방지를 위한 대기
                if chunk_count < (total_pages // self.MAX_PAGES_PER_REQUEST + 1):
                    time.sleep(2)  # 청크 간 2초 대기

            finally:
                # 임시 파일 삭제
                Path(temp_path).unlink(missing_ok=True)

        logger.info(
            f"✅ Split parsing completed: "
            f"{chunk_count} chunks, {len(all_elements)} total elements"
        )

        # 병합된 결과 반환
        return {
            "api": "2.0",
            "model": "document-parse-250618",
            "usage": {"pages": total_pages},
            "content": {
                "html": "",  # 분할 파싱 시 전체 HTML은 생략
                "markdown": "",
                "text": "",
            },
            "elements": all_elements,
            "metadata": {
                "split_parsing": True,
                "total_chunks": chunk_count,
                "pages_per_chunk": self.MAX_PAGES_PER_REQUEST,
            },
        }

    def _parse_single_pdf(self, pdf_path: str, retries: int = 3) -> Dict[str, Any]:
        """
        단일 PDF 파싱 (Upstage API 직접 호출)

        Args:
            pdf_path: PDF 파일 경로
            retries: 재시도 횟수

        Returns:
            API 응답 JSON

        Raises:
            Exception: API 호출 실패 시
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = {
            "ocr": "force",
            "base64_encoding": "['table']",
            "model": "document-parse",
        }

        for attempt in range(retries):
            try:
                with open(pdf_path, "rb") as f:
                    files = {"document": f}
                    response = requests.post(
                        self.url, headers=headers, files=files, data=data, timeout=120
                    )

                if response.status_code == 200:
                    result = response.json()
                    element_count = len(result.get("elements", []))
                    pages_count = result.get("usage", {}).get("pages", 0)
                    logger.info(
                        f"✅ API returned {element_count} elements from {pages_count} pages"
                    )
                    return result
                elif response.status_code == 429:  # Rate limit
                    if attempt < retries - 1:
                        wait_time = 2**attempt
                        logger.warning(
                            f"⏳ Rate limited, waiting {wait_time}s before retry"
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded: {response.text}")
                else:
                    raise Exception(
                        f"API call failed: {response.status_code} - {response.text}"
                    )

            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    logger.warning(f"Request failed, retrying: {e}")
                    time.sleep(2**attempt)
                    continue
                else:
                    raise Exception(f"API request failed after {retries} retries: {e}")

        raise Exception("API call failed after all retries")
````

## File: backend/search/search_service.py
````python
"""
Books Assistant - 검색 서비스
계층형 벡터 검색 및 메타데이터 필터링
"""

import logging
from typing import List, Dict, Any, Optional

from backend.storage.hierarchical_vector_store import (
    HierarchicalVectorStore,
    SearchMode,
    load_chapter_summaries,
    load_page_summaries,
)

logger = logging.getLogger(__name__)


class SearchService:
    """
    통합 검색 서비스

    벡터 검색 + 메타데이터 필터링
    """

    def __init__(self, vector_store: Optional[HierarchicalVectorStore] = None):
        """
        초기화

        Args:
            vector_store: HierarchicalVectorStore 인스턴스 (옵션)
        """
        self.vector_store = vector_store
        self.chapter_summaries = []
        self.page_summaries = []

        logger.info("SearchService initialized")

    def initialize(
        self,
        chapter_summaries_dir: str = "output/summaries",
        page_cache_dir: str = "cache/summaries",
        rebuild_index: bool = False,
    ) -> None:
        """
        검색 서비스 초기화

        Args:
            chapter_summaries_dir: 챕터 요약 디렉토리
            page_cache_dir: 페이지 캐시 디렉토리
            rebuild_index: 벡터 인덱스 재생성 여부
        """
        logger.info("Initializing search service...")

        # 1. 요약 데이터 로드
        logger.info("Loading summaries...")
        self.chapter_summaries = load_chapter_summaries(chapter_summaries_dir)
        self.page_summaries = load_page_summaries(page_cache_dir)

        # 2. 벡터 스토어 초기화
        if self.vector_store is None:
            self.vector_store = HierarchicalVectorStore()

        # 3. 벡터 인덱스 생성 또는 로드
        if rebuild_index:
            logger.info("Building vector index...")
            self.vector_store.build_index(self.chapter_summaries, self.page_summaries)
            self.vector_store.save()
        else:
            try:
                logger.info("Loading existing vector index...")
                self.vector_store.load()
            except FileNotFoundError:
                logger.info("No existing index found. Building new index...")
                self.vector_store.build_index(
                    self.chapter_summaries, self.page_summaries
                )
                self.vector_store.save()

        logger.info("Search service ready!")

    def search(
        self,
        query: str,
        mode: SearchMode = "drilldown",
        k: int = 5,
        chapter_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        통합 검색

        Args:
            query: 검색 쿼리
            mode: 검색 모드 (chapter/page/drilldown)
            k: 결과 개수
            chapter_filter: 챕터 필터 (예: "ch3")

        Returns:
            검색 결과
        """
        if self.vector_store is None:
            raise ValueError("Search service not initialized. Call initialize() first.")

        logger.info(f"Search query: '{query}' (mode={mode}, k={k})")

        results = self.vector_store.search(
            query=query, mode=mode, k=k, chapter_filter=chapter_filter
        )

        return {
            "query": query,
            "mode": mode,
            "results": results,
            "result_count": len(results),
        }

    def search_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """
        키워드 기반 검색 (메타데이터, 비용 0)

        Args:
            keyword: 검색 키워드

        Returns:
            매칭된 챕터 리스트
        """
        logger.info(f"Keyword search: '{keyword}'")

        results = []
        keyword_lower = keyword.lower()

        for chapter in self.chapter_summaries:
            # 키워드 매칭
            if any(keyword_lower in kw.lower() for kw in chapter.keywords):
                results.append(
                    {
                        "chapter_id": chapter.chapter_id,
                        "chapter_title": chapter.chapter_title,
                        "keywords": chapter.keywords,
                        "match_type": "keyword",
                        "summary": chapter.summary,
                    }
                )
            # Summary 매칭
            elif keyword_lower in chapter.summary.lower():
                results.append(
                    {
                        "chapter_id": chapter.chapter_id,
                        "chapter_title": chapter.chapter_title,
                        "keywords": chapter.keywords,
                        "match_type": "summary",
                        "summary": chapter.summary,
                    }
                )

        logger.info(f"Keyword search: {len(results)} results")
        return results

    def get_chapter_by_id(self, chapter_id: str) -> Optional[Dict[str, Any]]:
        """
        챕터 ID로 조회

        Args:
            chapter_id: 챕터 ID (예: "ch1")

        Returns:
            챕터 정보
        """
        for chapter in self.chapter_summaries:
            if chapter.chapter_id == chapter_id:
                return chapter.model_dump()
        return None
````

## File: backend/storage/document_builder.py
````python
"""
Books Assistant - Document 변환 유틸리티
ChapterSummary, PageSummary를 LangChain Document로 변환
"""

from typing import List
from langchain_core.documents import Document

from backend.summarizers.page_summary_cache import PageSummary
from backend.summarizers.chapter_merger import ChapterSummary


class DocumentBuilder:
    """요약 객체를 LangChain Document로 변환"""

    @staticmethod
    def chapter_summary_to_document(chapter: ChapterSummary) -> Document:
        """
        ChapterSummary → Document 변환

        Args:
            chapter: ChapterSummary 객체

        Returns:
            LangChain Document
        """
        # 검색 가능한 텍스트 구성
        content_parts = [
            f"# {chapter.chapter_title}",
            "",
            f"## Summary",
            chapter.summary,
            "",
            f"## Keywords",
            ", ".join(chapter.keywords),
            "",
            f"## Key Facts",
        ]

        # Facts 추가 (최대 5개만 - 임베딩 효율)
        for fact in chapter.facts[:5]:
            content_parts.append(f"- {fact}")

        # Claims 추가
        if chapter.claims:
            content_parts.append("")
            content_parts.append("## Main Claims")
            for claim in chapter.claims[:3]:
                content_parts.append(f"- {claim}")

        page_content = "\n".join(content_parts)

        # 메타데이터
        metadata = {
            "level": "chapter",
            "chapter_id": chapter.chapter_id,
            "chapter_title": chapter.chapter_title,
            "start_page": chapter.start_page,
            "end_page": chapter.end_page,
            "page_count": chapter.page_count,
            "keywords": chapter.keywords,
        }

        return Document(page_content=page_content, metadata=metadata)

    @staticmethod
    def page_summary_to_document(page: PageSummary) -> Document:
        """
        PageSummary → Document 변환

        Args:
            page: PageSummary 객체

        Returns:
            LangChain Document
        """
        # 검색 가능한 텍스트 구성
        content_parts = [
            f"Page {page.page} (Chapter {page.chapter_id})",
            "",
            page.summary,
            "",
            "Facts:",
        ]

        for fact in page.facts:
            content_parts.append(f"- {fact}")

        page_content = "\n".join(content_parts)

        # 메타데이터
        metadata = {
            "level": "page",
            "chapter_id": page.chapter_id,
            "page": page.page,
        }

        return Document(page_content=page_content, metadata=metadata)

    @classmethod
    def build_all_documents(
        cls, chapter_summaries: List[ChapterSummary], page_summaries: List[PageSummary]
    ) -> List[Document]:
        """
        전체 Document 생성 (챕터 + 페이지)

        Args:
            chapter_summaries: ChapterSummary 리스트
            page_summaries: PageSummary 리스트

        Returns:
            Document 리스트 (챕터 9개 + 페이지 343개)
        """
        documents = []

        # 챕터 Document 생성
        for chapter in chapter_summaries:
            doc = cls.chapter_summary_to_document(chapter)
            documents.append(doc)

        # 페이지 Document 생성
        for page in page_summaries:
            doc = cls.page_summary_to_document(page)
            documents.append(doc)

        return documents
````

## File: backend/storage/hierarchical_vector_store.py
````python
"""
Books Assistant - 계층형 벡터 스토어
챕터(9) + 페이지(343) 계층 임베딩 및 검색
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal

from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

from backend.config.settings import settings
from backend.storage.document_builder import DocumentBuilder
from backend.summarizers.page_summary_cache import PageSummary
from backend.summarizers.chapter_merger import ChapterSummary

logger = logging.getLogger(__name__)


SearchMode = Literal["chapter", "page", "drilldown"]


class HierarchicalVectorStore:
    """
    계층형 벡터 스토어

    챕터(9개) + 페이지(343개) 임베딩으로 드릴다운 검색 지원
    """

    def __init__(
        self,
        embedding_model: str = "text-embedding-3-small",
        vector_store_path: Optional[str] = None,
    ):
        """
        초기화

        Args:
            embedding_model: OpenAI 임베딩 모델
            vector_store_path: 벡터 스토어 저장 경로
        """
        self.embedding_model = embedding_model
        self.embeddings = OpenAIEmbeddings(
            model=embedding_model, api_key=settings.openai_api_key
        )

        self.vector_store_path = (
            Path(vector_store_path) if vector_store_path else Path("cache/vectors")
        )
        self.vector_store_path.mkdir(parents=True, exist_ok=True)

        self.vectorstore: Optional[FAISS] = None
        self.document_builder = DocumentBuilder()

        logger.info(f"HierarchicalVectorStore initialized")
        logger.info(f"  Embedding model: {embedding_model}")
        logger.info(f"  Cache path: {self.vector_store_path}")

    def build_index(
        self, chapter_summaries: List[ChapterSummary], page_summaries: List[PageSummary]
    ) -> None:
        """
        챕터 + 페이지 임베딩 생성

        Args:
            chapter_summaries: ChapterSummary 리스트 (9개)
            page_summaries: PageSummary 리스트 (343개)
        """
        logger.info("=" * 80)
        logger.info("Building hierarchical vector index...")
        logger.info("=" * 80)

        # Document 변환
        logger.info(f"Step 1: Converting summaries to documents...")
        documents = self.document_builder.build_all_documents(
            chapter_summaries, page_summaries
        )

        chapter_count = len(chapter_summaries)
        page_count = len(page_summaries)
        total_count = len(documents)

        logger.info(f"Created {total_count} documents")
        logger.info(f"  - Chapters: {chapter_count}")
        logger.info(f"  - Pages: {page_count}")

        # 임베딩 생성
        logger.info(f"\nStep 2: Creating embeddings (OpenAI {self.embedding_model})...")
        logger.info(f"  This may take a moment...")

        self.vectorstore = FAISS.from_documents(documents, self.embeddings)

        logger.info(f"Embeddings created")
        logger.info(f"  Total vectors: {total_count}")

        logger.info("=" * 80)
        logger.info("Vector index build completed!")
        logger.info("=" * 80)

    def save(self, filename: str = "hierarchical_vectors") -> Path:
        """
        벡터 스토어 저장

        Args:
            filename: 저장 파일명 (확장자 제외)

        Returns:
            저장된 파일 경로
        """
        if self.vectorstore is None:
            raise ValueError("Vector store not built. Call build_index() first.")

        save_path = self.vector_store_path / filename
        self.vectorstore.save_local(str(save_path))

        logger.info(f"Vector store saved to {save_path}")
        return save_path

    def load(self, filename: str = "hierarchical_vectors") -> None:
        """
        벡터 스토어 로드

        Args:
            filename: 로드할 파일명 (확장자 제외)
        """
        load_path = self.vector_store_path / filename

        if not load_path.exists():
            raise FileNotFoundError(f"Vector store not found: {load_path}")

        self.vectorstore = FAISS.load_local(
            str(load_path), self.embeddings, allow_dangerous_deserialization=True
        )

        logger.info(f"Vector store loaded from {load_path}")

    def search(
        self,
        query: str,
        mode: SearchMode = "drilldown",
        k: int = 5,
        chapter_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        계층형 검색

        Args:
            query: 검색 쿼리
            mode: 검색 모드
                - "chapter": 챕터만 검색
                - "page": 페이지만 검색
                - "drilldown": 챕터 → 관련 페이지 (계층 탐색)
            k: 반환할 결과 개수
            chapter_filter: 특정 챕터로 제한 (예: "ch3")

        Returns:
            검색 결과 리스트
        """
        if self.vectorstore is None:
            raise ValueError(
                "Vector store not initialized. Call build_index() or load() first."
            )

        if mode == "chapter":
            return self._search_chapters(query, k)

        elif mode == "page":
            return self._search_pages(query, k, chapter_filter)

        elif mode == "drilldown":
            return self._search_drilldown(query, k)

        else:
            raise ValueError(
                f"Invalid mode: {mode}. Use 'chapter', 'page', or 'drilldown'."
            )

    def _search_chapters(self, query: str, k: int = 3) -> List[Dict[str, Any]]:
        """
        챕터만 검색

        Args:
            query: 검색 쿼리
            k: 반환할 챕터 개수

        Returns:
            챕터 검색 결과
        """
        # 챕터 레벨만 필터링
        results = self.vectorstore.similarity_search_with_score(
            query, k=k * 3, filter={"level": "chapter"}  # 오버샘플링 후 필터링
        )

        # 상위 k개만 반환
        formatted_results = []
        for doc, score in results[:k]:
            formatted_results.append(
                {
                    "type": "chapter",
                    "chapter_id": doc.metadata["chapter_id"],
                    "chapter_title": doc.metadata["chapter_title"],
                    "page_range": f"{doc.metadata['start_page']}-{doc.metadata['end_page']}",
                    "keywords": doc.metadata["keywords"],
                    "score": float(score),
                    "content": doc.page_content[:200] + "...",  # 미리보기
                }
            )

        logger.info(f"Chapter search: {len(formatted_results)} results")
        return formatted_results

    def _search_pages(
        self, query: str, k: int = 5, chapter_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        페이지만 검색

        Args:
            query: 검색 쿼리
            k: 반환할 페이지 개수
            chapter_filter: 특정 챕터로 제한

        Returns:
            페이지 검색 결과
        """
        # 필터 구성
        search_filter = {"level": "page"}
        if chapter_filter:
            search_filter["chapter_id"] = chapter_filter

        # 페이지 레벨만 검색
        results = self.vectorstore.similarity_search_with_score(
            query, k=k, filter=search_filter
        )

        # 결과 포맷팅
        formatted_results = []
        for doc, score in results:
            formatted_results.append(
                {
                    "type": "page",
                    "chapter_id": doc.metadata["chapter_id"],
                    "page": doc.metadata["page"],
                    "score": float(score),
                    "content": doc.page_content,
                }
            )

        logger.info(f"Page search: {len(formatted_results)} results")
        return formatted_results

    def _search_drilldown(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        드릴다운 검색: 챕터 → 관련 페이지

        Args:
            query: 검색 쿼리
            k: 챕터당 반환할 페이지 개수

        Returns:
            챕터별 관련 페이지 그룹
        """
        logger.info(f"Drilldown search for: '{query}'")

        # 1단계: 관련 챕터 찾기 (상위 3개)
        chapters = self._search_chapters(query, k=3)

        # 2단계: 각 챕터의 관련 페이지 찾기
        drilldown_results = []

        for chapter in chapters:
            chapter_id = chapter["chapter_id"]

            # 해당 챕터 내에서만 페이지 검색
            pages = self._search_pages(query, k=k, chapter_filter=chapter_id)

            drilldown_results.append(
                {"chapter": chapter, "related_pages": pages, "page_count": len(pages)}
            )

        logger.info(f"Drilldown search completed: {len(drilldown_results)} chapters")
        return drilldown_results

    def get_statistics(self) -> Dict[str, Any]:
        """
        벡터 스토어 통계

        Returns:
            통계 정보
        """
        if self.vectorstore is None:
            return {"status": "not_initialized"}

        # FAISS 인덱스 크기 확인
        total_vectors = self.vectorstore.index.ntotal

        return {
            "status": "initialized",
            "total_vectors": total_vectors,
            "embedding_model": self.embedding_model,
            "vector_store_path": str(self.vector_store_path),
        }


# =============================================================================
# 편의 함수
# =============================================================================


def load_chapter_summaries(
    summaries_dir: str = "output/summaries",
) -> List[ChapterSummary]:
    """
    챕터 요약 파일 로드

    Args:
        summaries_dir: 요약 파일 디렉토리

    Returns:
        ChapterSummary 리스트
    """
    summaries_path = Path(summaries_dir)
    chapter_files = sorted(summaries_path.glob("chapter*_hierarchical_summary.json"))

    chapter_summaries = []
    for file in chapter_files:
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            chapter_summaries.append(ChapterSummary(**data))

    logger.info(f"Loaded {len(chapter_summaries)} chapter summaries")
    return chapter_summaries


def load_page_summaries(cache_dir: str = "cache/summaries") -> List[PageSummary]:
    """
    페이지 요약 캐시 로드

    Args:
        cache_dir: 캐시 디렉토리

    Returns:
        PageSummary 리스트
    """
    cache_path = Path(cache_dir)
    cache_files = sorted(cache_path.glob("ch*_page*.json"))

    page_summaries = []
    for file in cache_files:
        with open(file, "r", encoding="utf-8") as f:
            data = json.load(f)
            # 캐시 파일 구조: {"summary": {PageSummary data}, ...}
            page_summaries.append(PageSummary(**data["summary"]))

    logger.info(f"Loaded {len(page_summaries)} page summaries")
    return page_summaries
````

## File: backend/structure/chapter_detector.py
````python
"""
챕터 경계 탐지 모듈

레이아웃 신호와 텍스트 패턴을 결합하여 챕터 경계를 탐지합니다.
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ChapterDetector:
    """챕터 경계 탐지 클래스"""

    # 챕터 제목 패턴 (확장됨)
    CHAPTER_PATTERNS = {
        # 한글 패턴
        "korean_chapter_full": (re.compile(r"^제\s*(\d+)\s*장"), 50),  # 제1장
        "korean_chapter_short": (re.compile(r"^(\d+)\s*장$"), 50),  # 1장, 2장 (단독)
        "korean_part": (re.compile(r"^제\s*(\d+)\s*부"), 55),  # 제1부 (상위 계층)
        # 영어 패턴
        "english_chapter": (re.compile(r"^CHAPTER\s+(\d+)", re.IGNORECASE), 50),
        "english_part": (re.compile(r"^Part\s+(\d+)", re.IGNORECASE), 55),
        # 번호 패턴
        "numbered_title": (
            re.compile(r"^(\d+)\.\s+([가-힣a-zA-Z].{3,})"),
            35,
        ),  # 1. 제목
    }

    # 레이아웃 임계값
    MIN_CHAPTER_SPACING = 3  # 챕터 간 최소 페이지 간격
    LARGE_FONT_THRESHOLD = 16  # 큰 폰트 기준 (16px 이상)
    SCORE_THRESHOLD = 55  # 챕터 확정 점수 (낮춤)

    def __init__(self):
        """챕터 탐지기 초기화"""
        pass

    def detect_chapters(
        self, parsed_data: Dict[str, Any], main_pages: List[int]
    ) -> List[Dict[str, Any]]:
        """
        챕터 경계 탐지

        Args:
            parsed_data: PDF 파싱 결과
            main_pages: 본문 페이지 목록

        Returns:
            [
                {
                    "id": "ch1",
                    "number": 1,
                    "title": "제1장 의식의 본질",
                    "start_page": 4,
                    "end_page": 25,
                    "score": 85.0,
                    "detection_method": "korean_chapter"
                },
                ...
            ]
        """
        logger.info(f"🔍 Detecting chapters in {len(main_pages)} main pages...")

        pages = parsed_data.get("pages", [])

        # Main 페이지만 필터링
        main_page_objects = [p for p in pages if p["page_number"] in main_pages]

        # 1. 챕터 제목 후보 탐지
        candidates = []
        for page in main_page_objects:
            page_candidates = self._find_chapter_candidates(page)
            candidates.extend(page_candidates)

        logger.info(f"  Found {len(candidates)} chapter title candidates")

        # 2. 점수 기반 필터링
        chapters = []
        for candidate in candidates:
            if candidate["score"] >= self.SCORE_THRESHOLD:
                chapters.append(candidate)
                logger.info(
                    f"    ✓ Chapter {candidate['number']}: '{candidate['title']}' "
                    f"(page {candidate['start_page']}, score: {candidate['score']:.1f})"
                )

        # 3. 품질 검증 및 정제
        chapters = self._validate_and_refine_chapters(chapters, main_pages)

        logger.info(f"✅ Detected {len(chapters)} chapters")
        return chapters

    def _find_chapter_candidates(self, page: Dict) -> List[Dict[str, Any]]:
        """
        페이지에서 챕터 제목 후보 찾기
        """
        candidates = []
        elements = page.get("elements", [])

        for elem in elements:
            text = elem.get("text", "").strip()
            if not text:  # 빈 문자열만 제외 (한글 챕터 "1장"=2글자 허용)
                continue

            # 텍스트 패턴 매칭
            for pattern_name, (pattern, base_score) in self.CHAPTER_PATTERNS.items():
                match = pattern.match(text)
                if match:
                    # 점수 계산
                    score = self._calculate_chapter_score(
                        elem, pattern_name, base_score
                    )

                    # 챕터 번호 및 제목 추출
                    groups = match.groups()
                    chapter_number = int(groups[0]) if groups[0].isdigit() else 0
                    chapter_title = groups[1].strip() if len(groups) > 1 else text

                    candidates.append(
                        {
                            "id": f"ch{chapter_number}",
                            "number": chapter_number,
                            "title": text,
                            "start_page": page["page_number"],
                            "end_page": None,  # 나중에 설정
                            "score": score,
                            "detection_method": pattern_name,
                            "element": elem,
                        }
                    )
                    break

        return candidates

    def _calculate_chapter_score(
        self, elem: Dict, pattern_name: str, base_score: float
    ) -> float:
        """
        챕터 제목 후보의 점수 계산

        점수 구성:
        - 텍스트 패턴 점수: 35-55점 (base_score)
        - 레이아웃 점수: 0-45점
          - 큰 폰트 크기: +25점 (강화)
          - 페이지 상단 배치: +20점 (강화)
          - 카테고리가 heading: +15점
          - 짧은 텍스트: +10점 (챕터 제목은 짧음)
        """
        score = base_score

        # 레이아웃 점수
        font_size = elem.get("font_size", 12)
        bbox = elem.get("bbox", {})
        category = elem.get("category", "")
        text = elem.get("text", "").strip()
        y0 = bbox.get("y0", 0.5)

        # 1. 큰 폰트 (강화)
        if font_size >= 20:
            score += 30  # 매우 큰 폰트
        elif font_size >= self.LARGE_FONT_THRESHOLD:
            score += 20  # 큰 폰트

        # 2. 페이지 상단 배치 (강화)
        if y0 < 0.1:
            score += 25  # 맨 위
        elif y0 < 0.2:
            score += 20  # 상단

        # 3. Heading 카테고리
        if category in ["heading", "heading1", "title"]:
            score += 15

        # 4. 짧은 텍스트 (챕터 제목은 대부분 짧음)
        if len(text) <= 20:  # "1장", "제1장 제목" 등
            score += 10

        return min(100.0, score)

    def _validate_and_refine_chapters(
        self, chapters: List[Dict], main_pages: List[int]
    ) -> List[Dict]:
        """
        챕터 목록 검증 및 정제

        - 챕터 번호 순서대로 정렬
        - 중복 제거
        - 최소 간격 확인
        - end_page 설정
        """
        if not chapters:
            return []

        # 1. 챕터 번호 순서대로 정렬
        chapters = sorted(chapters, key=lambda x: x["number"])

        # 2. 중복 제거 (같은 번호의 챕터는 점수가 높은 것만)
        unique_chapters = {}
        for ch in chapters:
            ch_num = ch["number"]
            if (
                ch_num not in unique_chapters
                or ch["score"] > unique_chapters[ch_num]["score"]
            ):
                unique_chapters[ch_num] = ch

        chapters = list(unique_chapters.values())
        chapters = sorted(chapters, key=lambda x: x["number"])

        # 3. 최소 간격 확인
        filtered = []
        for i, ch in enumerate(chapters):
            # 이전 챕터와의 간격 확인
            if (
                filtered
                and ch["start_page"] - filtered[-1]["start_page"]
                < self.MIN_CHAPTER_SPACING
            ):
                logger.warning(
                    f"  ⚠️ Skipping chapter {ch['number']} - too close to previous chapter "
                    f"({ch['start_page'] - filtered[-1]['start_page']} pages apart)"
                )
                continue

            filtered.append(ch)

        # 4. end_page 설정
        for i, ch in enumerate(filtered):
            if i < len(filtered) - 1:
                ch["end_page"] = filtered[i + 1]["start_page"] - 1
            else:
                ch["end_page"] = main_pages[-1] if main_pages else ch["start_page"]

        return filtered
````

## File: backend/structure/content_boundary_detector.py
````python
"""
본문 영역 탐지 모듈

Intro (표지, 서문) / Main (본문) / Notes (참고문헌, 부록) 영역을 분리합니다.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from backend.structure.footer_analyzer import FooterAnalyzer

logger = logging.getLogger(__name__)


class ContentBoundaryDetector:
    """본문 영역 경계 탐지 클래스"""

    # Pre Body 키워드 (확장됨)
    PRE_BODY_KEYWORDS = [
        # 한글
        "작가",
        "작가 소개",
        "저자",
        "저자 소개",
        "저자소개",
        "지은이",
        "추천",
        "추천의 글",
        "추천사",
        "추천하는 말",
        "서문",
        "머리말",
        "프롤로그",
        "들어가며",
        "시작하며",
        "감사의 글",
        "감사",
        "헌정",
        "표지",
        "판권",
        "저작권",
        "차례",
        "목차",
        # 영어
        "author",
        "about the author",
        "recommendation",
        "foreword",
        "preface",
        "prologue",
        "introduction",
        "acknowledgment",
        "dedication",
        "copyright",
        "contents",
        "table of contents",
    ]

    # Post Body 키워드 (확장됨)
    POST_BODY_KEYWORDS = [
        # 한글
        "맺음말",
        "끝맺음",
        "나가며",
        "마치며",
        "에필로그",
        "결론",
        "주",
        "각주",
        "미주",
        "참고 주",
        "주석",
        "참고문헌",
        "참고자료",
        "문헌",
        "bibliography",
        "부록",
        "색인",
        "용어집",
        "출판",
        "출판사",
        "출판정보",
        # 영어
        "epilogue",
        "conclusion",
        "closing",
        "endnote",
        "endnotes",
        "notes",
        "footnote",
        "references",
        "bibliography",
        "appendix",
        "appendices",
        "index",
        "glossary",
        "publisher",
        "publishing",
    ]

    # 본문 시작 패턴 (확장됨)
    MAIN_START_PATTERNS = [
        # 챕터 패턴
        re.compile(r"제\s*1\s*장"),  # 제1장
        re.compile(r"제\s*1\s*부"),  # 제1부
        re.compile(r"CHAPTER\s+[1I]", re.IGNORECASE),  # Chapter 1, Chapter I
        re.compile(r"Part\s+[1I]", re.IGNORECASE),  # Part 1, Part I
        re.compile(r"^1\s*장"),  # 1장
        re.compile(r"^1\.\s+[가-힣a-zA-Z]"),  # 1. 제목
        # 서론 패턴
        re.compile(r"^서론$"),  # 서론
        re.compile(r"^Introduction$", re.IGNORECASE),  # Introduction
        re.compile(r"^들어가며$"),  # 들어가며
        re.compile(r"^시작하며$"),  # 시작하며
    ]

    # 본문 단락 최소 길이
    MIN_PARAGRAPH_LENGTH = 100

    def __init__(self):
        """경계 탐지기 초기화"""
        self.footer_analyzer = FooterAnalyzer()

    def detect_boundaries(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        서문(start)/본문(main)/종문(end) 경계 탐지

        Returns:
            {
                "start": {"start": 1, "end": 3, "pages": [1,2,3]},
                "main": {"start": 4, "end": 95, "pages": [4,5,...,95]},
                "end": {"start": 96, "end": 100, "pages": [96,97,98,99,100]},
                "confidence": {"start": 0.9, "main": 1.0, "end": 0.8}
            }
        """
        logger.info("🔍 Detecting content boundaries (서문/본문/종문)...")

        pages = parsed_data.get("pages", [])
        if not pages:
            return self._default_result()

        # 0. Footer 정보 분석 (보조 수단)
        footer_info = self.footer_analyzer.analyze(parsed_data)

        # 1. 본문 시작 페이지 탐지
        main_start = self._detect_main_start(pages, footer_info)

        # 2. 종문 시작 페이지 탐지
        end_start = self._detect_notes_start(pages, main_start, footer_info)

        # 3. 경계 확정
        start_pages = list(range(1, main_start))
        main_end = end_start - 1 if end_start else len(pages)
        main_pages = list(range(main_start, main_end + 1))
        end_pages = list(range(end_start, len(pages) + 1)) if end_start else []

        result = {
            "start": {
                "start": start_pages[0] if start_pages else None,
                "end": start_pages[-1] if start_pages else None,
                "pages": start_pages,
            },
            "main": {
                "start": main_pages[0] if main_pages else 1,
                "end": main_pages[-1] if main_pages else len(pages),
                "pages": main_pages,
            },
            "end": {
                "start": end_pages[0] if end_pages else None,
                "end": end_pages[-1] if end_pages else None,
                "pages": end_pages,
            },
            "confidence": {
                "start": 0.8 if start_pages else 0.0,
                "main": 1.0,
                "end": 0.8 if end_pages else 0.0,
            },
        }

        logger.info(f"✅ Boundaries detected:")
        logger.info(
            f"   서문(start): pages {start_pages[0] if start_pages else None}-{start_pages[-1] if start_pages else None} ({len(start_pages)} pages)"
        )
        logger.info(
            f"   본문(main):  pages {main_pages[0]}-{main_pages[-1]} ({len(main_pages)} pages)"
        )
        logger.info(
            f"   종문(end): pages {end_pages[0] if end_pages else None}-{end_pages[-1] if end_pages else None} ({len(end_pages)} pages)"
        )

        return result

    def _detect_main_start(self, pages: List[Dict], footer_info: Dict) -> int:
        """
        본문 시작 페이지 탐지

        Returns:
            본문 시작 페이지 번호 (1-indexed)
        """
        logger.info("  → Detecting main content start...")

        best_score = 0.0
        best_page = 3  # 최소 3페이지부터 시작 (표지 제외)

        for page in pages:
            page_num = page["page_number"]

            # 표지는 제외 (1-2페이지)
            if page_num <= 2:
                continue

            score = self._calculate_main_start_score(page, footer_info)

            if score > best_score:
                best_score = score
                best_page = page_num

        # Footer 힌트로 추가 검증
        chapter_hints = footer_info.get("chapter_hints", [])
        if chapter_hints and best_score < 0.6:
            # 챕터 힌트가 있으면 그 부근을 우선
            first_chapter_page = min(chapter_hints)
            if first_chapter_page >= 3:
                logger.info(
                    f"     Using footer hint: first chapter at page {first_chapter_page}"
                )
                best_page = first_chapter_page

        logger.info(f"     Main starts at page {best_page} (score: {best_score:.2f})")
        return best_page

    def _detect_notes_start(
        self, pages: List[Dict], main_start: int, footer_info: Dict
    ) -> Optional[int]:
        """
        종문 시작 페이지 탐지 (3단계 계층적 필터링)

        Phase 1: Footer 요소 우선 검사 (단어 경계 매칭)
        Phase 2: 제목 형태 Element 검사 (짧은 텍스트 + 큰 폰트 + 상단)
        Phase 3: 전체 텍스트 검사 (fallback, 단어 경계 매칭)

        Args:
            main_start: 본문 시작 페이지
            footer_info: Footer 분석 정보

        Returns:
            종문 시작 페이지 번호 또는 None
        """
        logger.info("  → Detecting notes/post-body section start...")

        # Footer 힌트 먼저 확인
        post_body_start = footer_info.get("post_body_start")
        if post_body_start and post_body_start > main_start:
            logger.info(
                f"     Using footer hint: post-body starts at page {post_body_start}"
            )
            return post_body_start

        # 본문 후반부만 검사 (전체의 50% 이후)
        search_start_idx = max(main_start, int(len(pages) * 0.5))
        logger.info(
            f"     Searching from page {pages[search_start_idx]['page_number']} (50% of total)"
        )

        # Phase 1: Footer 우선 검사
        result = self._check_footer_elements(pages, search_start_idx)
        if result:
            return result

        # Phase 2: 제목 형태 Element 검사
        result = self._check_title_like_elements(pages, search_start_idx)
        if result:
            return result

        # Phase 3: 전체 텍스트 검사 (fallback)
        result = self._check_full_text(pages, search_start_idx)
        if result:
            return result

        logger.info(f"     No post-body section detected")
        return None

    def _check_footer_elements(
        self, pages: List[Dict], start_idx: int
    ) -> Optional[int]:
        """Phase 1: Footer 요소만 검사 (단어 경계 매칭)"""
        logger.info("     Phase 1: Checking footer elements...")

        for page in pages[start_idx:]:
            page_num = page["page_number"]
            footer_elements = [
                e for e in page.get("elements", []) if e.get("category") == "footer"
            ]

            for elem in footer_elements:
                text = elem.get("text", "").strip()

                for keyword in self.POST_BODY_KEYWORDS:
                    # 단어 경계 매칭 (\b = word boundary)
                    pattern = r"\b" + re.escape(keyword) + r"\b"
                    if re.search(pattern, text, re.IGNORECASE):
                        logger.info(
                            f"     ✓ Found in footer at page {page_num}: "
                            f"keyword='{keyword}', text='{text[:50]}...'"
                        )
                        return page_num

        return None

    def _check_title_like_elements(
        self, pages: List[Dict], start_idx: int
    ) -> Optional[int]:
        """Phase 2: 제목 형태 Element 검사 (짧은 텍스트 + 큰 폰트 + 상단)"""
        logger.info("     Phase 2: Checking title-like elements...")

        for page in pages[start_idx:]:
            page_num = page["page_number"]
            elements = page.get("elements", [])

            if not elements:
                continue

            # 페이지 맨 위 요소들만 검사 (상위 20%)
            top_elements = []
            for elem in elements:
                bbox = elem.get("bbox", {})
                y0 = bbox.get("y0", 1.0)
                if y0 < 0.2:  # 상단 20% 이내
                    top_elements.append(elem)

            for elem in top_elements:
                text = elem.get("text", "").strip()
                font_size = elem.get("font_size", 12)
                text_length = len(text)

                # 제목 조건: 짧고(≤50자) + 큰 폰트(≥14px)
                if text_length <= 50 and font_size >= 14:
                    for keyword in self.POST_BODY_KEYWORDS:
                        # 단어 경계 매칭
                        pattern = r"\b" + re.escape(keyword) + r"\b"
                        if re.search(pattern, text, re.IGNORECASE):
                            logger.info(
                                f"     ✓ Found title-like at page {page_num}: "
                                f"keyword='{keyword}', text='{text}', "
                                f"font_size={font_size}, length={text_length}"
                            )
                            return page_num

        return None

    def _check_full_text(self, pages: List[Dict], start_idx: int) -> Optional[int]:
        """Phase 3: 전체 텍스트 검사 (fallback, 단어 경계 매칭)"""
        logger.info("     Phase 3: Checking full text (fallback)...")

        best_page = None
        best_score = 0.0

        for page in pages[start_idx:]:
            page_num = page["page_number"]
            page_text = " ".join(
                [elem.get("text", "") for elem in page.get("elements", [])]
            )

            for keyword in self.POST_BODY_KEYWORDS:
                # 단어 경계 매칭
                pattern = r"\b" + re.escape(keyword) + r"\b"
                if re.search(pattern, page_text, re.IGNORECASE):
                    # 키워드 중요도에 따라 점수 부여
                    if keyword in [
                        "맺음말",
                        "에필로그",
                        "epilogue",
                        "각주",
                        "미주",
                        "endnote",
                        "참고문헌",
                        "references",
                    ]:
                        score = 1.0
                    else:
                        score = 0.7

                    if score > best_score:
                        best_score = score
                        best_page = page_num
                        logger.info(
                            f"     Post-body candidate at page {best_page} "
                            f"(keyword: '{keyword}', score: {score:.2f})"
                        )
                        break

            # 점수가 높으면 바로 리턴
            if best_score >= 1.0:
                break

        if best_page:
            logger.info(f"     ✓ Post-body starts at page {best_page} (full text match)")
            return best_page

        return None

    def _calculate_main_start_score(self, page: Dict, footer_info: Dict) -> float:
        """
        본문 시작 가능성 점수 계산

        점수 구성:
        - 본문 패턴 매칭: 50% (0.5점)
        - 긴 단락 존재: 30% (0.3점)
        - Footer 힌트: 20% (0.2점)
        - Pre Body 키워드 페널티: -0.4점
        """
        elements = page.get("elements", [])
        page_text = " ".join([elem.get("text", "") for elem in elements])
        page_num = page.get("page_number", 0)

        score = 0.0

        # 1. 본문 시작 패턴 확인 (50%)
        if any(pattern.search(page_text) for pattern in self.MAIN_START_PATTERNS):
            score += 0.5

        # 2. 긴 단락 확인 (30%)
        has_long_paragraph = any(
            len(elem.get("text", "")) >= self.MIN_PARAGRAPH_LENGTH
            for elem in elements
            if elem.get("category") == "paragraph"
        )
        if has_long_paragraph:
            score += 0.3

        # 3. Footer 힌트 (20%)
        chapter_hints = footer_info.get("chapter_hints", [])
        if page_num in chapter_hints:
            score += 0.2

        # 4. Pre Body 키워드 페널티
        has_pre_body_keyword = any(
            keyword.lower() in page_text.lower() for keyword in self.PRE_BODY_KEYWORDS
        )
        if has_pre_body_keyword:
            score = max(0, score - 0.4)

        return min(1.0, score)

    def _default_result(self) -> Dict[str, Any]:
        """기본 결과 (탐지 실패 시)"""
        return {
            "start": {"start": None, "end": None, "pages": []},
            "main": {"start": 1, "end": 1, "pages": [1]},
            "end": {"start": None, "end": None, "pages": []},
            "confidence": {"start": 0.0, "main": 0.0, "end": 0.0},
        }
````

## File: backend/structure/footer_analyzer.py
````python
"""
Footer 분석 모듈

Footer 정보를 추출하여 섹션 변화 힌트를 제공합니다.
⚠️ Footer는 보조 수단으로만 사용 (상위 계층 표시 가능)
"""

import re
import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class FooterAnalyzer:
    """Footer 분석 클래스"""

    # Pre Body 관련 키워드
    PRE_BODY_KEYWORDS = [
        "작가",
        "저자",
        "author",
        "추천",
        "추천의 글",
        "추천사",
        "recommendation",
        "서문",
        "머리말",
        "foreword",
        "preface",
        "감사",
        "acknowledgment",
        "헌정",
        "dedication",
    ]

    # Post Body 관련 키워드
    POST_BODY_KEYWORDS = [
        "맺음말",
        "에필로그",
        "epilogue",
        "conclusion",
        "주",
        "각주",
        "미주",
        "endnote",
        "note",
        "참고문헌",
        "references",
        "bibliography",
        "부록",
        "appendix",
        "색인",
        "index",
        "용어집",
        "glossary",
    ]

    # 챕터 관련 키워드
    CHAPTER_KEYWORDS = [
        "장",
        "chapter",
        "부",
        "part",
    ]

    def __init__(self):
        """초기화"""
        self.footer_data = defaultdict(dict)  # {page: {section_name, page_number}}
        self.section_changes = []  # [(page, old_section, new_section)]
        self.section_hints = defaultdict(list)  # {section_type: [pages]}

    def analyze(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        전체 Footer 정보 분석

        Args:
            parsed_data: PDFParser.parse_pdf() 결과

        Returns:
            {
                "footer_data": {page: {section_name, page_number}},
                "section_changes": [(page, old, new)],
                "pre_body_hints": [pages],
                "post_body_hints": [pages],
                "chapter_hints": [pages]
            }
        """
        logger.info("📑 Analyzing footer information...")

        pages = parsed_data.get("pages", [])

        # 1. 모든 페이지의 Footer 추출
        for page_data in pages:
            self._extract_page_footer(page_data)

        # 2. 섹션 변화 감지
        self._detect_section_changes()

        # 3. 섹션 타입별 힌트 분류
        self._classify_section_hints()

        # Post Body 시작 페이지 추정
        post_body_start = self.get_post_body_start()

        result = {
            "footer_data": dict(self.footer_data),
            "section_changes": self.section_changes,
            "pre_body_hints": self.section_hints.get("pre_body", []),
            "post_body_hints": self.section_hints.get("post_body", []),
            "post_body_start": post_body_start,  # 추가
            "chapter_hints": self.section_hints.get("chapter", []),
        }

        logger.info(f"   Footers found: {len(self.footer_data)} pages")
        logger.info(f"   Section changes: {len(self.section_changes)}")
        logger.info(f"   Pre-body hints: {len(result['pre_body_hints'])} pages")
        logger.info(f"   Post-body hints: {len(result['post_body_hints'])} pages")
        logger.info(f"   Post-body start: {post_body_start}")
        logger.info(f"   Chapter hints: {len(result['chapter_hints'])} pages")

        return result

    def _extract_page_footer(self, page_data: Dict) -> None:
        """단일 페이지의 Footer 추출"""
        page_num = page_data.get("page", 0)
        elements = page_data.get("elements", [])

        section_name = None
        page_number = None

        # Footer 요소 찾기
        for elem in elements:
            if elem.get("category") == "footer":
                text = elem.get("text", "").strip()
                bbox = elem.get("bbox", {})
                y_position = bbox.get("y0", 0)

                # 페이지 하단 (y > 0.9) 확인
                if y_position > 0.85:  # 하단 15% 영역
                    # 섹션명 추출 (페이지 번호가 아닌 텍스트)
                    if text and not text.isdigit() and len(text) > 1:
                        # 숫자만 있는 경우 제외
                        if not re.match(r"^[\d\s\-]+$", text):
                            section_name = text

                    # 페이지 번호 추출
                    page_num_match = re.search(r"\d+", text)
                    if page_num_match:
                        page_number = int(page_num_match.group())

        # Footer 정보 저장
        if section_name or page_number:
            self.footer_data[page_num] = {
                "section_name": section_name,
                "page_number": page_number,
            }

    def _detect_section_changes(self) -> None:
        """섹션 변화 감지"""
        sorted_pages = sorted(self.footer_data.keys())
        prev_section = None

        for page in sorted_pages:
            curr_section = self.footer_data[page].get("section_name")

            if curr_section and curr_section != prev_section:
                self.section_changes.append(
                    {
                        "page": page,
                        "old_section": prev_section,
                        "new_section": curr_section,
                    }
                )
                prev_section = curr_section

    def _classify_section_hints(self) -> None:
        """섹션 타입별 힌트 분류"""
        for page, footer_info in self.footer_data.items():
            section_name = footer_info.get("section_name")
            if not section_name:
                continue

            section_lower = section_name.lower()

            # Pre Body 키워드 매칭
            for keyword in self.PRE_BODY_KEYWORDS:
                if keyword.lower() in section_lower:
                    self.section_hints["pre_body"].append(page)
                    break

            # Post Body 키워드 매칭
            for keyword in self.POST_BODY_KEYWORDS:
                if keyword.lower() in section_lower:
                    self.section_hints["post_body"].append(page)
                    break

            # Chapter 키워드 매칭
            for keyword in self.CHAPTER_KEYWORDS:
                if keyword.lower() in section_lower:
                    self.section_hints["chapter"].append(page)
                    break

    def get_section_hint_for_page(self, page: int, tolerance: int = 2) -> Optional[str]:
        """
        특정 페이지의 섹션 힌트 조회 (±tolerance 페이지 범위)

        Args:
            page: 조회할 페이지
            tolerance: 앞뒤 페이지 범위

        Returns:
            "pre_body", "post_body", "chapter", None
        """
        for page_offset in range(-tolerance, tolerance + 1):
            check_page = page + page_offset
            if check_page in self.footer_data:
                section_name = self.footer_data[check_page].get("section_name")
                if section_name:
                    section_lower = section_name.lower()

                    # Pre Body 체크
                    for keyword in self.PRE_BODY_KEYWORDS:
                        if keyword.lower() in section_lower:
                            return "pre_body"

                    # Post Body 체크
                    for keyword in self.POST_BODY_KEYWORDS:
                        if keyword.lower() in section_lower:
                            return "post_body"

                    # Chapter 체크
                    for keyword in self.CHAPTER_KEYWORDS:
                        if keyword.lower() in section_lower:
                            return "chapter"

        return None

    def get_pre_body_range(self) -> Optional[tuple]:
        """Pre Body 페이지 범위 추정"""
        pre_pages = self.section_hints.get("pre_body", [])
        if pre_pages:
            return (min(pre_pages), max(pre_pages))
        return None

    def get_post_body_start(self) -> Optional[int]:
        """Post Body 시작 페이지 추정"""
        post_pages = self.section_hints.get("post_body", [])
        if post_pages:
            return min(post_pages)
        return None
````

## File: backend/structure/hierarchy_builder.py
````python
"""
소제목 계층 구조 파악 모듈

챕터 내부의 섹션, 소제목 계층을 분석합니다.
"""

import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


class HierarchyBuilder:
    """계층 구조 분석 클래스"""

    # 섹션 번호 패턴
    SECTION_PATTERNS = {
        "decimal_1": (re.compile(r"^(\d+\.\d+)\s+(.+)"), 1),  # 1.1 제목
        "decimal_2": (re.compile(r"^(\d+\.\d+\.\d+)\s+(.+)"), 2),  # 1.1.1 제목
        "korean_list": (re.compile(r"^([가-하])\.\s+(.+)"), 1),  # 가. 제목
        "paren_number": (re.compile(r"^\((\d+)\)\s+(.+)"), 2),  # (1) 제목
    }

    # 폰트 크기 기준
    NORMAL_FONT_SIZE = 12
    SECTION_FONT_THRESHOLD = 14

    def __init__(self):
        """계층 분석기 초기화"""
        pass

    def build_hierarchy(
        self, parsed_data: Dict[str, Any], chapters: List[Dict]
    ) -> List[Dict]:
        """
        챕터별 계층 구조 생성

        Args:
            parsed_data: PDF 파싱 결과
            chapters: 탐지된 챕터 목록

        Returns:
            챕터 목록 (각 챕터에 sections 추가)
        """
        logger.info(f"🔍 Building hierarchy for {len(chapters)} chapters...")

        pages = parsed_data.get("pages", [])

        for chapter in chapters:
            start = chapter["start_page"]
            end = chapter["end_page"]

            # 챕터 페이지 추출
            chapter_pages = [p for p in pages if start <= p["page_number"] <= end]

            # 섹션 탐지
            sections = self._detect_sections(chapter_pages)
            chapter["sections"] = sections

            logger.info(
                f"  Chapter {chapter['number']}: {len(sections)} sections "
                f"(pages {start}-{end})"
            )

        logger.info(f"✅ Hierarchy built")
        return chapters

    def _detect_sections(self, chapter_pages: List[Dict]) -> List[Dict]:
        """
        챕터 내 섹션 탐지
        """
        sections = []

        for page in chapter_pages:
            elements = page.get("elements", [])

            for elem in elements:
                text = elem.get("text", "").strip()
                if not text or len(text) < 3:
                    continue

                # 패턴 매칭
                for pattern_name, (pattern, level) in self.SECTION_PATTERNS.items():
                    match = pattern.match(text)
                    if match:
                        groups = match.groups()
                        section_number = groups[0]
                        section_title = groups[1].strip() if len(groups) > 1 else text

                        # 폰트 크기 확인
                        font_size = elem.get("font_size", self.NORMAL_FONT_SIZE)
                        is_prominent = font_size >= self.SECTION_FONT_THRESHOLD

                        sections.append(
                            {
                                "id": f"s{section_number}".replace(".", "_"),
                                "number": section_number,
                                "title": text,
                                "level": level,
                                "page": page["page_number"],
                                "font_size": font_size,
                                "is_prominent": is_prominent,
                            }
                        )
                        break

        return sections
````

## File: backend/structure/structure_builder.py
````python
"""
전체 구조 통합 모듈

서문(start)/본문(main)/종문(end)를 통합하여 최종 구조 JSON을 생성합니다.
"""

import logging
from typing import Dict, Any

from backend.structure.content_boundary_detector import ContentBoundaryDetector
from backend.structure.chapter_detector import ChapterDetector
from backend.structure.hierarchy_builder import HierarchyBuilder

logger = logging.getLogger(__name__)


class StructureBuilder:
    """전체 구조 통합 클래스"""

    def __init__(self):
        """구조 빌더 초기화"""
        self.boundary_detector = ContentBoundaryDetector()
        self.chapter_detector = ChapterDetector()
        self.hierarchy_builder = HierarchyBuilder()

    def build_structure(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        전체 구조 분석 파이프라인

        Args:
            parsed_data: PDFParser.parse_pdf() 결과

        Returns:
            {
                "start": {"pages": [1,2,3], "page_count": 3},
                "main": {
                    "pages": [4, 5, ..., 95],
                    "page_count": 92,
                    "chapters": [
                        {
                            "id": "ch1",
                            "number": 1,
                            "title": "제1장 의식의 본질",
                            "start_page": 4,
                            "end_page": 25,
                            "sections": [...]
                        },
                        ...
                    ]
                },
                "end": {"pages": [96, ..., 100], "page_count": 5},
                "metadata": {
                    "total_pages": 100,
                    "chapter_count": 5,
                    "has_start": True,
                    "has_end": True
                }
            }
        """
        logger.info("=" * 80)
        logger.info("🏗️ Building complete book structure...")
        logger.info("=" * 80)

        # 1. 영역 경계 탐지 (서문/본문/종문)
        boundaries = self.boundary_detector.detect_boundaries(parsed_data)

        # 2. 챕터 탐지 (본문 영역에서)
        main_pages = boundaries["main"]["pages"]
        chapters = self.chapter_detector.detect_chapters(parsed_data, main_pages)

        # 3. 계층 구조 구축 (각 챕터 내 섹션)
        chapters = self.hierarchy_builder.build_hierarchy(parsed_data, chapters)

        # 4. 최종 구조 생성
        structure = {
            "start": {
                "pages": boundaries["start"]["pages"],
                "page_count": len(boundaries["start"]["pages"]),
            },
            "main": {
                "pages": main_pages,
                "page_count": len(main_pages),
                "chapters": chapters,
            },
            "end": {
                "pages": boundaries["end"]["pages"],
                "page_count": len(boundaries["end"]["pages"]),
            },
            "metadata": {
                "total_pages": parsed_data.get("total_pages", 0),
                "chapter_count": len(chapters),
                "has_start": len(boundaries["start"]["pages"]) > 0,
                "has_end": len(boundaries["end"]["pages"]) > 0,
                "confidence": boundaries.get("confidence", {}),
            },
        }

        logger.info("=" * 80)
        logger.info("✅ Structure building completed!")
        logger.info(f"   서문(start): {structure['start']['page_count']} pages")
        logger.info(
            f"   본문(main):  {structure['main']['page_count']} pages ({len(chapters)} chapters)"
        )
        logger.info(f"   종문(end): {structure['end']['page_count']} pages")
        logger.info("=" * 80)

        return structure
````

## File: backend/summarizers/batch_processor.py
````python
"""
Books Assistant - 배치 처리 및 병렬화
비동기 페이지 요약으로 성능 향상
"""

import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime

from langchain_core.documents import Document

from backend.summarizers.page_summarizer import PageSummarizer, PageSummary

logger = logging.getLogger(__name__)


class AsyncPageSummarizer:
    """비동기 페이지 요약기"""

    def __init__(self, page_summarizer: PageSummarizer, max_concurrent: int = 5):
        """
        초기화

        Args:
            page_summarizer: PageSummarizer 인스턴스
            max_concurrent: 동시 실행 최대 개수
        """
        self.page_summarizer = page_summarizer
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

        logger.info(f"AsyncPageSummarizer initialized: max_concurrent={max_concurrent}")

    async def summarize_page_async(
        self, page_doc: Document, use_cache: bool = True
    ) -> PageSummary:
        """
        비동기 페이지 요약

        Args:
            page_doc: 페이지 Document
            use_cache: 캐시 사용 여부

        Returns:
            PageSummary 객체
        """
        async with self.semaphore:
            # 동기 함수를 비동기로 래핑
            loop = asyncio.get_event_loop()
            summary = await loop.run_in_executor(
                None, self.page_summarizer.summarize_page, page_doc, use_cache
            )
            return summary

    async def summarize_pages_async(
        self, page_docs: List[Document], use_cache: bool = True
    ) -> List[PageSummary]:
        """
        비동기 배치 페이지 요약

        Args:
            page_docs: 페이지 Document 리스트
            use_cache: 캐시 사용 여부

        Returns:
            PageSummary 리스트
        """
        logger.info(f"Starting async batch summarization: {len(page_docs)} pages")
        logger.info(f"  Max concurrent tasks: {self.max_concurrent}")

        start_time = datetime.now()

        # 비동기 태스크 생성
        tasks = [
            self.summarize_page_async(page_doc, use_cache) for page_doc in page_docs
        ]

        # 모든 태스크 실행 (진행 상황 모니터링)
        summaries = await asyncio.gather(*tasks, return_exceptions=True)

        # 에러 처리
        errors = []
        valid_summaries = []

        for i, result in enumerate(summaries):
            if isinstance(result, Exception):
                page_num = page_docs[i].metadata.get("page", "?")
                logger.error(f"Error summarizing page {page_num}: {result}")
                errors.append({"page": page_num, "error": str(result)})
            else:
                valid_summaries.append(result)

        elapsed = (datetime.now() - start_time).total_seconds()

        logger.info(f"✓ Async batch summarization completed")
        logger.info(f"  Successful: {len(valid_summaries)}/{len(page_docs)}")
        logger.info(f"  Errors: {len(errors)}")
        logger.info(f"  Elapsed time: {elapsed:.2f}s")
        logger.info(f"  Avg time per page: {elapsed / len(page_docs):.2f}s")

        if errors:
            logger.warning(f"⚠️ {len(errors)} pages failed to summarize")

        return valid_summaries


class BatchProcessor:
    """배치 처리 유틸리티"""

    @staticmethod
    def chunk_documents(
        documents: List[Document], chunk_size: int
    ) -> List[List[Document]]:
        """
        Document 리스트를 청크로 분할

        Args:
            documents: Document 리스트
            chunk_size: 청크 크기

        Returns:
            청크 리스트
        """
        chunks = []
        for i in range(0, len(documents), chunk_size):
            chunks.append(documents[i : i + chunk_size])

        logger.info(f"Split {len(documents)} documents into {len(chunks)} chunks")
        return chunks

    @staticmethod
    async def process_in_batches(
        page_docs: List[Document],
        page_summarizer: PageSummarizer,
        batch_size: int = 10,
        max_concurrent: int = 5,
        use_cache: bool = True,
    ) -> List[PageSummary]:
        """
        배치 단위로 순차 처리

        Args:
            page_docs: 페이지 Document 리스트
            page_summarizer: PageSummarizer 인스턴스
            batch_size: 배치 크기
            max_concurrent: 배치 내 동시 실행 수
            use_cache: 캐시 사용 여부

        Returns:
            PageSummary 리스트
        """
        logger.info(f"Processing {len(page_docs)} pages in batches")
        logger.info(f"  Batch size: {batch_size}")
        logger.info(f"  Concurrent per batch: {max_concurrent}")

        # 청크 분할
        chunks = BatchProcessor.chunk_documents(page_docs, batch_size)

        # 비동기 요약기
        async_summarizer = AsyncPageSummarizer(
            page_summarizer, max_concurrent=max_concurrent
        )

        all_summaries = []

        # 배치별 순차 처리
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"\nProcessing batch {i}/{len(chunks)} ({len(chunk)} pages)...")

            batch_summaries = await async_summarizer.summarize_pages_async(
                chunk, use_cache=use_cache
            )

            all_summaries.extend(batch_summaries)

            logger.info(f"✓ Batch {i} completed: {len(batch_summaries)} summaries")

        logger.info(f"\n✓ All batches completed: {len(all_summaries)} total summaries")
        return all_summaries


def summarize_pages_parallel(
    page_docs: List[Document],
    page_summarizer: PageSummarizer,
    max_concurrent: int = 5,
    use_cache: bool = True,
) -> List[PageSummary]:
    """
    병렬 페이지 요약 편의 함수 (동기 인터페이스)

    Args:
        page_docs: 페이지 Document 리스트
        page_summarizer: PageSummarizer 인스턴스
        max_concurrent: 동시 실행 최대 개수
        use_cache: 캐시 사용 여부

    Returns:
        PageSummary 리스트
    """
    async_summarizer = AsyncPageSummarizer(
        page_summarizer, max_concurrent=max_concurrent
    )

    # asyncio 이벤트 루프 실행
    return asyncio.run(async_summarizer.summarize_pages_async(page_docs, use_cache))
````

## File: backend/summarizers/chapter_merger.py
````python
"""
Books Assistant - 챕터 병합기
페이지 요약들을 종합하여 챕터 전체 요약 생성
"""

from typing import List
import logging

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from backend.summarizers.page_summary_cache import PageSummary
from backend.config.settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic 모델
# =============================================================================


class ChapterSummary(BaseModel):
    """챕터 요약 구조체"""

    chapter_id: str = Field(description="챕터 ID")
    chapter_title: str = Field(description="챕터 제목")

    facts: list[str] = Field(
        description="챕터 전체의 핵심 사실들 (최대 10개)",
        max_length=10,
        default_factory=list,
    )

    claims: list[str] = Field(
        description="챕터 전체의 주장/논점들 (최대 5개)",
        max_length=5,
        default_factory=list,
    )

    examples: list[str] = Field(
        description="챕터 전체의 예시/사례들 (최대 5개)",
        max_length=5,
        default_factory=list,
    )

    quotes: list[str] = Field(
        description="핵심 인용문 (10단어 이하, 최대 3개)",
        max_length=3,
        default_factory=list,
    )

    keywords: list[str] = Field(
        description="챕터 핵심 키워드/개념 (3-5개)",
        min_length=3,
        max_length=5,
        default_factory=list,
    )

    summary: str = Field(
        description="챕터 전체 요약 (100-200자)", min_length=50, max_length=500
    )

    page_count: int = Field(description="총 페이지 수")
    start_page: int = Field(description="시작 페이지")
    end_page: int = Field(description="종료 페이지")


# =============================================================================
# 프롬프트
# =============================================================================

CHAPTER_MERGE_PROMPT = """당신은 여러 페이지 요약을 종합하여 챕터 전체 요약을 생성하는 전문가입니다.

## 챕터 정보
- 챕터 제목: {chapter_title}
- 페이지 범위: {start_page}-{end_page} ({page_count}페이지)

## 페이지별 요약
{page_summaries}

## 요약 지침

주어진 페이지 요약들을 종합하여 챕터 전체의 핵심 내용을 추출하세요.

1. **Facts (핵심 사실)**
   - 여러 페이지에 걸쳐 언급된 중요한 사실들
   - 중복 제거, 중요도 순 정렬
   - 최대 10개

2. **Claims (주장/논점)**
   - 챕터 전체를 관통하는 저자의 주장
   - 페이지별 내용을 종합하여 도출
   - 최대 5개

3. **Examples (예시/사례)**
   - 챕터에서 사용된 구체적 사례
   - 최대 5개

4. **Quotes (핵심 인용문)**
   - 챕터를 대표하는 핵심 문장
   - 10단어 이하
   - 최대 3개

5. **Keywords (핵심 키워드)**
   - 챕터의 핵심 개념/용어
   - 3-5개

6. **Summary (챕터 전체 요약)**
   - 100-200자로 챕터 전체 내용 요약
   - 챕터의 핵심 메시지 전달

## 주의사항
- 페이지 요약들 간의 연결성을 파악하세요
- 중복된 내용은 통합하세요
- 챕터 전체의 흐름과 맥락을 고려하세요
- 원문의 의미를 왜곡하지 마세요
"""


# =============================================================================
# 챕터 병합기
# =============================================================================


class ChapterMerger:
    """페이지 요약을 챕터 요약으로 병합"""

    def __init__(self, model: str = None, temperature: float = None):
        """
        초기화

        Args:
            model: OpenAI 모델 이름
            temperature: 생성 온도
        """
        self.model_name = model or settings.openai_model
        self.temperature = (
            temperature if temperature is not None else settings.openai_temperature
        )

        # LLM 초기화
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            api_key=settings.openai_api_key,
        ).with_structured_output(ChapterSummary)

        # 프롬프트
        self.prompt = ChatPromptTemplate.from_template(CHAPTER_MERGE_PROMPT)

        # 체인 구성
        self.chain = self.prompt | self.llm

        logger.info(f"ChapterMerger initialized: model={self.model_name}")

    def merge_page_summaries(
        self,
        page_summaries: List[PageSummary],
        chapter_id: str,
        chapter_title: str,
        start_page: int,
        end_page: int,
    ) -> ChapterSummary:
        """
        페이지 요약들을 챕터 요약으로 병합

        Args:
            page_summaries: PageSummary 리스트
            chapter_id: 챕터 ID
            chapter_title: 챕터 제목
            start_page: 시작 페이지
            end_page: 종료 페이지

        Returns:
            ChapterSummary 객체
        """
        logger.info(f"Merging {len(page_summaries)} page summaries for {chapter_id}...")

        # 페이지 요약을 텍스트로 포맷팅
        page_summaries_text = self._format_page_summaries(page_summaries)

        # 입력 데이터 준비
        input_data = {
            "chapter_title": chapter_title,
            "start_page": start_page,
            "end_page": end_page,
            "page_count": len(page_summaries),
            "page_summaries": page_summaries_text,
        }

        try:
            # LLM 호출
            chapter_summary = self.chain.invoke(input_data)

            # 메타데이터 추가
            chapter_summary.chapter_id = chapter_id
            chapter_summary.chapter_title = chapter_title
            chapter_summary.page_count = len(page_summaries)
            chapter_summary.start_page = start_page
            chapter_summary.end_page = end_page

            logger.info(f"✓ Chapter {chapter_id} summary created")
            return chapter_summary

        except Exception as e:
            logger.error(f"Error merging chapter {chapter_id}: {e}")
            raise

    def _format_page_summaries(self, page_summaries: List[PageSummary]) -> str:
        """
        페이지 요약들을 텍스트로 포맷팅

        Args:
            page_summaries: PageSummary 리스트

        Returns:
            포맷팅된 텍스트
        """
        formatted_lines = []

        for ps in page_summaries:
            formatted_lines.append(f"[Page {ps.page}]")
            formatted_lines.append(f"Facts: {', '.join(ps.facts)}")
            formatted_lines.append(f"Summary: {ps.summary}")
            formatted_lines.append("")  # 빈 줄

        return "\n".join(formatted_lines)
````

## File: backend/summarizers/document_loaders.py
````python
"""
Books Assistant - LangChain Document Loader
파싱된 PDF 결과를 LangChain Document 객체로 변환
"""

from langchain_core.documents import Document
from typing import List, Dict, Any, Iterator, Optional
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class BookDocumentLoader:
    """
    PDF 파싱 결과와 구조 분석 결과를 LangChain Document로 변환
    
    입력:
    - parsing_result: output/tests/parsing_result_clean.json
    - structure_result: output/tests/structure_result.json
    
    출력:
    - LangChain Document 리스트 (메타데이터 포함)
    """
    
    def __init__(
        self,
        parsing_result_path: str = "output/tests/parsing_result_clean.json",
        structure_result_path: str = "output/tests/structure_result.json"
    ):
        self.parsing_result_path = Path(parsing_result_path)
        self.structure_result_path = Path(structure_result_path)
        
        self.parsing_data: Optional[Dict[str, Any]] = None
        self.structure_data: Optional[Dict[str, Any]] = None
        self.page_elements: Dict[int, List[Dict[str, Any]]] = {}
    
    def _load_data(self) -> None:
        """파싱 결과와 구조 분석 결과 로드"""
        logger.info(f"Loading parsing result from {self.parsing_result_path}")
        with open(self.parsing_result_path, 'r', encoding='utf-8') as f:
            self.parsing_data = json.load(f)
        
        logger.info(f"Loading structure result from {self.structure_result_path}")
        with open(self.structure_result_path, 'r', encoding='utf-8') as f:
            self.structure_data = json.load(f)
        
        # 페이지별 element 인덱싱 (빠른 조회를 위해)
        if self.parsing_data and self.parsing_data.get("success"):
            for page_data in self.parsing_data.get("pages", []):
                page_num = page_data.get("page_number")
                self.page_elements[page_num] = page_data.get("elements", [])
        
        logger.info(f"Loaded {len(self.page_elements)} pages with elements")
    
    def _extract_text_from_pages(
        self, 
        start_page: int, 
        end_page: int,
        filter_categories: Optional[List[str]] = None
    ) -> str:
        """
        페이지 범위에서 텍스트 추출
        
        Args:
            start_page: 시작 페이지
            end_page: 종료 페이지
            filter_categories: 포함할 element 카테고리 (None이면 전체)
        
        Returns:
            추출된 텍스트
        """
        texts = []
        
        for page_num in range(start_page, end_page + 1):
            if page_num not in self.page_elements:
                logger.warning(f"Page {page_num} not found in parsing result")
                continue
            
            elements = self.page_elements[page_num]
            for element in elements:
                # 카테고리 필터링
                if filter_categories and element.get("category") not in filter_categories:
                    continue
                
                text = element.get("text", "").strip()
                if text:
                    texts.append(text)
        
        return "\n".join(texts)
    
    def _extract_element_ids(
        self, 
        start_page: int, 
        end_page: int
    ) -> List[int]:
        """페이지 범위의 모든 element ID 수집"""
        element_ids = []
        
        for page_num in range(start_page, end_page + 1):
            if page_num not in self.page_elements:
                continue
            
            elements = self.page_elements[page_num]
            element_ids.extend([elem.get("id") for elem in elements if "id" in elem])
        
        return element_ids
    
    def _create_chapter_document(self, chapter: Dict[str, Any]) -> Document:
        """챕터 정보를 Document로 변환"""
        chapter_id = chapter.get("id", "unknown")
        chapter_number = chapter.get("number", 0)
        chapter_title = chapter.get("title", "")
        start_page = chapter.get("start_page", 0)
        end_page = chapter.get("end_page", 0)
        
        # 챕터 텍스트 추출 (paragraph, heading 카테고리만)
        text_content = self._extract_text_from_pages(
            start_page, 
            end_page,
            filter_categories=["paragraph", "heading1", "heading2", "heading3"]
        )
        
        # element ID 수집
        element_ids = self._extract_element_ids(start_page, end_page)
        
        # Document 생성
        doc = Document(
            page_content=text_content,
            metadata={
                "node_id": chapter_id,
                "node_type": "chapter",
                "chapter_id": chapter_id,
                "chapter_number": chapter_number,
                "chapter_title": chapter_title,
                "start_page": start_page,
                "end_page": end_page,
                "page_count": end_page - start_page + 1,
                "level": 0,  # 챕터는 레벨 0
                "element_ids": element_ids,
                "detection_method": chapter.get("detection_method", ""),
                "score": chapter.get("score", 0.0)
            }
        )
        
        return doc
    
    def _create_section_document(
        self, 
        section: Dict[str, Any], 
        chapter: Dict[str, Any]
    ) -> Document:
        """섹션 정보를 Document로 변환"""
        section_id = section.get("id", "unknown")
        section_number = section.get("number", "")
        section_title = section.get("title", "")
        section_page = section.get("page", 0)
        section_level = section.get("level", 1)
        
        chapter_id = chapter.get("id", "unknown")
        chapter_number = chapter.get("number", 0)
        
        # 섹션은 단일 페이지 또는 다음 섹션까지의 범위
        # 현재는 섹션 페이지만 사용 (향후 확장 가능)
        text_content = self._extract_text_from_pages(
            section_page,
            section_page,
            filter_categories=["paragraph", "heading1", "heading2", "heading3"]
        )
        
        element_ids = self._extract_element_ids(section_page, section_page)
        
        # Document 생성
        doc = Document(
            page_content=text_content,
            metadata={
                "node_id": f"{chapter_id}_{section_id}",
                "node_type": "section",
                "chapter_id": chapter_id,
                "chapter_number": chapter_number,
                "section_id": section_id,
                "section_number": section_number,
                "section_title": section_title,
                "page": section_page,
                "level": section_level,
                "element_ids": element_ids,
                "font_size": section.get("font_size", 0),
                "is_prominent": section.get("is_prominent", False)
            }
        )
        
        return doc
    
    def _create_intro_document(self) -> Optional[Document]:
        """서문 Document 생성"""
        if not self.structure_data or "start" not in self.structure_data:
            return None
        
        start_section = self.structure_data["start"]
        pages = start_section.get("pages", [])
        
        if not pages:
            return None
        
        start_page = min(pages)
        end_page = max(pages)
        
        text_content = self._extract_text_from_pages(
            start_page,
            end_page,
            filter_categories=["paragraph", "heading1", "heading2", "heading3"]
        )
        
        element_ids = self._extract_element_ids(start_page, end_page)
        
        return Document(
            page_content=text_content,
            metadata={
                "node_id": "intro",
                "node_type": "intro",
                "start_page": start_page,
                "end_page": end_page,
                "page_count": len(pages),
                "level": -1,  # 서문은 레벨 -1
                "element_ids": element_ids
            }
        )
    
    def _create_end_document(self) -> Optional[Document]:
        """종문(참고문헌, 색인 등) Document 생성"""
        if not self.structure_data or "end" not in self.structure_data:
            return None
        
        end_section = self.structure_data["end"]
        pages = end_section.get("pages", [])
        
        if not pages:
            return None
        
        start_page = min(pages)
        end_page = max(pages)
        
        text_content = self._extract_text_from_pages(
            start_page,
            end_page,
            filter_categories=["paragraph", "heading1", "heading2", "heading3"]
        )
        
        element_ids = self._extract_element_ids(start_page, end_page)
        
        return Document(
            page_content=text_content,
            metadata={
                "node_id": "end",
                "node_type": "end",
                "start_page": start_page,
                "end_page": end_page,
                "page_count": len(pages),
                "level": -1,  # 종문도 레벨 -1
                "element_ids": element_ids
            }
        )
    
    def load(self) -> List[Document]:
        """
        전체 Document 리스트 반환
        
        Returns:
            Document 리스트
        """
        if not self.parsing_data or not self.structure_data:
            self._load_data()
        
        documents = []
        
        # 1. 서문 Document
        intro_doc = self._create_intro_document()
        if intro_doc:
            documents.append(intro_doc)
            logger.info(f"Created intro document ({intro_doc.metadata['page_count']} pages)")
        
        # 2. 챕터 Documents (섹션은 제외)
        main_section = self.structure_data.get("main", {})
        chapters = main_section.get("chapters", [])
        for chapter in chapters:
            # 챕터 Document만 생성
            chapter_doc = self._create_chapter_document(chapter)
            documents.append(chapter_doc)
            logger.info(
                f"Created chapter document: {chapter_doc.metadata['chapter_id']} "
                f"({chapter_doc.metadata['page_count']} pages)"
            )
        
        # 3. 종문 Document
        end_doc = self._create_end_document()
        if end_doc:
            documents.append(end_doc)
            logger.info(f"Created end document ({end_doc.metadata['page_count']} pages)")
        
        logger.info(f"Total documents created: {len(documents)}")
        return documents
    
    def lazy_load(self) -> Iterator[Document]:
        """
        메모리 효율적인 Document 생성 (Generator)
        
        Yields:
            Document 객체
        """
        if not self.parsing_data or not self.structure_data:
            self._load_data()
        
        # 1. 서문
        intro_doc = self._create_intro_document()
        if intro_doc:
            yield intro_doc
        
        # 2. 챕터 (섹션은 제외)
        main_section = self.structure_data.get("main", {})
        chapters = main_section.get("chapters", [])
        for chapter in chapters:
            yield self._create_chapter_document(chapter)
        
        # 3. 종문
        end_doc = self._create_end_document()
        if end_doc:
            yield end_doc


def load_book_documents(
    parsing_result_path: str = "output/tests/parsing_result_clean.json",
    structure_result_path: str = "output/tests/structure_result.json",
    lazy: bool = False
) -> List[Document] | Iterator[Document]:
    """
    편의 함수: 책 Document 로드
    
    Args:
        parsing_result_path: 파싱 결과 JSON 경로
        structure_result_path: 구조 분석 결과 JSON 경로
        lazy: True면 Generator 반환, False면 List 반환
    
    Returns:
        Document 리스트 또는 Generator
    """
    loader = BookDocumentLoader(parsing_result_path, structure_result_path)
    
    if lazy:
        return loader.lazy_load()
    else:
        return loader.load()
````

## File: backend/summarizers/hierarchical_summarizer.py
````python
"""
Books Assistant - 계층적 요약기
페이지 → 챕터 계층적 요약 파이프라인
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import logging
from datetime import datetime

from langchain_core.documents import Document

from backend.summarizers.document_loaders import load_book_documents
from backend.summarizers.page_splitter import PageSplitter
from backend.summarizers.page_summarizer import PageSummarizer
from backend.summarizers.page_summary_cache import PageSummary
from backend.summarizers.chapter_merger import ChapterMerger, ChapterSummary
from backend.summarizers.batch_processor import summarize_pages_parallel

logger = logging.getLogger(__name__)


class HierarchicalSummarizer:
    """
    계층적 요약 파이프라인

    1. 본문(챕터)만 필터링
    2. 챕터를 페이지별로 분할
    3. 페이지별 요약 생성 (캐싱)
    4. 페이지 요약을 챕터 요약으로 병합
    5. 결과 저장
    """

    def __init__(
        self,
        parsing_result_path: str = "output/tests/parsing_result_clean.json",
        structure_result_path: str = "output/tests/structure_result.json",
        output_dir: str = "output/summaries",
        enable_cache: bool = True,
    ):
        """
        초기화

        Args:
            parsing_result_path: 파싱 결과 경로
            structure_result_path: 구조 분석 결과 경로
            output_dir: 출력 디렉토리
            enable_cache: 캐싱 활성화
        """
        self.parsing_result_path = parsing_result_path
        self.structure_result_path = structure_result_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 컴포넌트 초기화
        self.page_splitter = PageSplitter(parsing_result_path)
        self.page_summarizer = PageSummarizer(enable_cache=enable_cache)
        self.chapter_merger = ChapterMerger()

        logger.info("=" * 80)
        logger.info("HierarchicalSummarizer initialized")
        logger.info(f"  Output directory: {self.output_dir}")
        logger.info(f"  Cache enabled: {enable_cache}")
        logger.info("=" * 80)

    def load_chapter_documents(
        self, chapter_filter: Optional[List[int]] = None
    ) -> List[Document]:
        """
        챕터 Document 로드 (본문만)

        Args:
            chapter_filter: 특정 챕터만 선택 (예: [1] → Chapter 1만)

        Returns:
            챕터 Document 리스트
        """
        logger.info("Loading documents...")

        # 전체 Document 로드
        all_documents = load_book_documents(
            parsing_result_path=self.parsing_result_path,
            structure_result_path=self.structure_result_path,
            lazy=False,
        )

        # 챕터만 필터링
        chapter_docs = [
            doc for doc in all_documents if doc.metadata.get("node_type") == "chapter"
        ]

        # 특정 챕터 필터링 (있는 경우)
        if chapter_filter:
            chapter_docs = [
                doc
                for doc in chapter_docs
                if doc.metadata.get("chapter_number") in chapter_filter
            ]

        logger.info(f"✓ Loaded {len(chapter_docs)} chapter(s)")
        for doc in chapter_docs:
            logger.info(
                f"  - {doc.metadata['chapter_id']}: "
                f"{doc.metadata['chapter_title']} "
                f"(pages {doc.metadata['start_page']}-{doc.metadata['end_page']})"
            )

        return chapter_docs

    def summarize_chapter(
        self,
        chapter_doc: Document,
        use_cache: bool = True,
        use_parallel: bool = True,
        max_concurrent: int = 5,
    ) -> Dict[str, Any]:
        """
        단일 챕터 요약

        Args:
            chapter_doc: 챕터 Document
            use_cache: 캐시 사용 여부
            use_parallel: 병렬 처리 여부
            max_concurrent: 동시 실행 최대 개수

        Returns:
            {
                "chapter_doc": Document,
                "page_docs": List[Document],
                "page_summaries": List[PageSummary],
                "chapter_summary": ChapterSummary
            }
        """
        chapter_id = chapter_doc.metadata["chapter_id"]
        chapter_title = chapter_doc.metadata["chapter_title"]

        logger.info("=" * 80)
        logger.info(f"Processing Chapter: {chapter_id} - {chapter_title}")
        logger.info("=" * 80)

        # 1. 페이지별 분할
        logger.info("Step 1: Splitting chapter into pages...")
        page_docs = self.page_splitter.split_chapter_to_pages(chapter_doc)
        logger.info(f"✓ Split into {len(page_docs)} pages")

        # 2. 페이지별 요약 (병렬 처리)
        if use_parallel:
            logger.info(
                f"Step 2: Summarizing pages in parallel (max {max_concurrent} concurrent, with caching)..."
            )
            page_summaries = summarize_pages_parallel(
                page_docs,
                self.page_summarizer,
                max_concurrent=max_concurrent,
                use_cache=use_cache,
            )
        else:
            logger.info("Step 2: Summarizing pages sequentially (with caching)...")
            page_summaries = self.page_summarizer.summarize_pages(
                page_docs, use_cache=use_cache
            )
        logger.info(f"✓ Created {len(page_summaries)} page summaries")

        # 3. 챕터 병합
        logger.info("Step 3: Merging page summaries into chapter summary...")
        chapter_summary = self.chapter_merger.merge_page_summaries(
            page_summaries=page_summaries,
            chapter_id=chapter_id,
            chapter_title=chapter_title,
            start_page=chapter_doc.metadata["start_page"],
            end_page=chapter_doc.metadata["end_page"],
        )
        logger.info(f"✓ Chapter summary created")

        return {
            "chapter_doc": chapter_doc,
            "page_docs": page_docs,
            "page_summaries": page_summaries,
            "chapter_summary": chapter_summary,
        }

    def summarize_all(
        self,
        chapter_filter: Optional[List[int]] = None,
        use_cache: bool = True,
        use_parallel: bool = True,
        max_concurrent: int = 5,
        save: bool = True,
        filename: str = "hierarchical_summaries.json",
    ) -> Dict[str, Any]:
        """
        전체 파이프라인 실행

        Args:
            chapter_filter: 특정 챕터만 선택 (예: [1] → Chapter 1만)
            use_cache: 캐시 사용 여부
            use_parallel: 병렬 처리 여부
            max_concurrent: 동시 실행 최대 개수
            save: 결과 저장 여부
            filename: 저장 파일명

        Returns:
            요약 결과
        """
        logger.info("=" * 80)
        logger.info("Starting Hierarchical Summarization Pipeline")
        logger.info("=" * 80)

        # 1. 챕터 Document 로드
        chapter_docs = self.load_chapter_documents(chapter_filter)

        # 2. 챕터별 요약
        results = []
        for i, chapter_doc in enumerate(chapter_docs, 1):
            logger.info(f"\n{'='*80}")
            logger.info(f"Processing Chapter {i}/{len(chapter_docs)}")
            logger.info(f"{'='*80}")

            chapter_result = self.summarize_chapter(
                chapter_doc,
                use_cache=use_cache,
                use_parallel=use_parallel,
                max_concurrent=max_concurrent,
            )
            results.append(chapter_result)

        # 3. 저장 (옵션)
        output_file = None
        if save:
            output_file = self.save_results(results, filename)

        # 4. 최종 결과
        final_result = {
            "chapter_docs": chapter_docs,
            "results": results,
            "chapter_summaries": [r["chapter_summary"] for r in results],
        }

        if output_file:
            final_result["output_file"] = output_file

        # 5. 요약 통계
        self._print_summary_statistics(results)

        logger.info("=" * 80)
        logger.info("✓ Hierarchical Summarization Pipeline Completed!")
        logger.info("=" * 80)

        return final_result

    def save_results(self, results: List[Dict[str, Any]], filename: str) -> Path:
        """
        결과 저장

        Args:
            results: 요약 결과 리스트
            filename: 저장 파일명

        Returns:
            저장된 파일 경로
        """
        output_file = self.output_dir / filename

        # JSON 직렬화 가능하도록 변환
        save_data = {
            "generated_at": datetime.now().isoformat(),
            "model": self.page_summarizer.model_name,
            "total_chapters": len(results),
            "chapters": [],
        }

        for result in results:
            chapter_summary = result["chapter_summary"]
            page_summaries = result["page_summaries"]

            save_data["chapters"].append(
                {
                    "chapter_id": chapter_summary.chapter_id,
                    "chapter_title": chapter_summary.chapter_title,
                    "start_page": chapter_summary.start_page,
                    "end_page": chapter_summary.end_page,
                    "page_count": chapter_summary.page_count,
                    "chapter_summary": chapter_summary.model_dump(),
                    "page_summaries": [ps.model_dump() for ps in page_summaries],
                }
            )

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✓ Results saved to {output_file}")
        return output_file

    def _print_summary_statistics(self, results: List[Dict[str, Any]]) -> None:
        """요약 통계 출력"""
        logger.info("\n" + "=" * 80)
        logger.info("SUMMARY STATISTICS")
        logger.info("=" * 80)

        total_pages = sum(len(r["page_summaries"]) for r in results)
        total_chapters = len(results)

        logger.info(f"Total Chapters: {total_chapters}")
        logger.info(f"Total Pages: {total_pages}")
        logger.info(f"Avg Pages per Chapter: {total_pages / total_chapters:.1f}")

        # 캐시 통계
        if self.page_summarizer.cache:
            cache_stats = self.page_summarizer.cache.get_cache_stats()
            logger.info(f"\nCache Statistics:")
            logger.info(f"  Total cached pages: {cache_stats['total_cached_pages']}")
            logger.info(f"  Chapters with cache:")
            for ch_id, count in cache_stats["chapters"].items():
                logger.info(f"    - {ch_id}: {count} pages")

        logger.info("=" * 80)
````

## File: backend/summarizers/llm_chains.py
````python
"""
Books Assistant - LangChain LLM 체인 구성
Structured Output with Pydantic을 활용한 요약 생성
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
import logging

from backend.config.settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic 모델 정의 (Structured Output)
# =============================================================================


class NodeSummary(BaseModel):
    """
    노드 요약 구조체

    LLM이 생성하는 요약의 구조화된 형식
    """

    node_id: str = Field(description="노드 식별자 (예: 'ch1', 'intro')")

    facts: List[str] = Field(
        description="객관적 사실들 (증명 가능한 정보, 데이터, 통계 등)",
        max_length=10,
        default_factory=list,
    )

    claims: List[str] = Field(
        description="주장/논점들 (저자의 의견, 주장, 해석 등)",
        max_length=5,
        default_factory=list,
    )

    examples: List[str] = Field(
        description="예시/사례들 (구체적 사례, 비유, 실험 결과 등)",
        max_length=5,
        default_factory=list,
    )

    quotes: List[str] = Field(
        description="핵심 인용문 (10단어 이하, 원문 그대로)",
        max_length=3,
        default_factory=list,
    )

    keywords: List[str] = Field(
        description="핵심 키워드/개념 (3-5개)",
        min_length=3,
        max_length=5,
        default_factory=list,
    )

    summary: str = Field(
        description="전체 요약 (3-5문장, 100-200자)", min_length=50, max_length=500
    )


# =============================================================================
# 프롬프트 템플릿
# =============================================================================

SUMMARIZATION_PROMPT = """당신은 학술 도서를 분석하는 전문가입니다.
주어진 텍스트를 읽고 구조화된 요약을 생성하세요.

## 텍스트 정보
- 노드 ID: {node_id}
- 노드 타입: {node_type}
- 페이지 범위: {page_info}

## 텍스트 내용
{content}

## 요약 지침

1. **Facts (객관적 사실)**
   - 증명 가능한 정보, 데이터, 통계, 역사적 사실
   - 예: "인간의 뇌는 약 860억 개의 뉴런으로 구성되어 있다"
   - 최대 10개

2. **Claims (주장/논점)**
   - 저자의 의견, 주장, 해석, 이론
   - 예: "의식은 뇌의 정보 통합 과정에서 발생한다"
   - 최대 5개

3. **Examples (예시/사례)**
   - 구체적 사례, 비유, 실험 결과, 현상 설명
   - 예: "파블로프의 개 실험에서..."
   - 최대 5개

4. **Quotes (핵심 인용문)**
   - 원문 그대로 인용 (10단어 이하)
   - 가장 중요한 문장만
   - 최대 3개

5. **Keywords (핵심 키워드)**
   - 이 텍스트의 핵심 개념/용어
   - 3-5개

6. **Summary (전체 요약)**
   - 3-5문장으로 전체 내용 요약
   - 100-200자
   - 핵심 메시지 전달

## 주의사항
- 원문의 의미를 왜곡하지 마세요
- 구체적이고 명확하게 작성하세요
- 중요도 순으로 정렬하세요
- 중복을 피하세요
"""


# =============================================================================
# LLM 체인 구성
# =============================================================================


class SummaryChain:
    """요약 생성 LLM 체인"""

    def __init__(self, model: str = None, temperature: float = None):
        """
        체인 초기화

        Args:
            model: OpenAI 모델 이름 (기본값: settings.openai_model)
            temperature: 생성 온도 (기본값: settings.openai_temperature)
        """
        self.model_name = model or settings.openai_model
        self.temperature = (
            temperature if temperature is not None else settings.openai_temperature
        )

        # LLM 초기화 (Structured Output)
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            api_key=settings.openai_api_key,
        ).with_structured_output(NodeSummary)

        # 프롬프트 템플릿
        self.prompt = ChatPromptTemplate.from_template(SUMMARIZATION_PROMPT)

        # 체인 구성 (LCEL)
        self.chain = self.prompt | self.llm

        logger.info(
            f"Initialized SummaryChain with model={self.model_name}, temperature={self.temperature}"
        )

    def summarize(self, document: Document) -> NodeSummary:
        """
        단일 Document 요약

        Args:
            document: LangChain Document 객체

        Returns:
            NodeSummary 객체
        """
        metadata = document.metadata

        # 페이지 정보 생성
        page_info = self._format_page_info(metadata)

        # 입력 데이터 준비
        input_data = {
            "node_id": metadata.get("node_id", "unknown"),
            "node_type": metadata.get("node_type", "unknown"),
            "page_info": page_info,
            "content": document.page_content,
        }

        logger.info(f"Summarizing document: {input_data['node_id']} ({page_info})")

        # LLM 호출
        try:
            summary = self.chain.invoke(input_data)
            logger.info(f"✓ Summary created for {input_data['node_id']}")
            return summary
        except Exception as e:
            logger.error(f"Error summarizing {input_data['node_id']}: {e}")
            raise

    def batch_summarize(self, documents: List[Document]) -> List[NodeSummary]:
        """
        배치 Document 요약

        Args:
            documents: Document 리스트

        Returns:
            NodeSummary 리스트
        """
        logger.info(f"Batch summarizing {len(documents)} documents...")

        # 입력 데이터 준비
        input_batch = []
        for doc in documents:
            metadata = doc.metadata
            page_info = self._format_page_info(metadata)

            input_batch.append(
                {
                    "node_id": metadata.get("node_id", "unknown"),
                    "node_type": metadata.get("node_type", "unknown"),
                    "page_info": page_info,
                    "content": doc.page_content,
                }
            )

        # 배치 LLM 호출
        try:
            summaries = self.chain.batch(input_batch)
            logger.info(f"✓ Batch summary completed: {len(summaries)} summaries")
            return summaries
        except Exception as e:
            logger.error(f"Error in batch summarization: {e}")
            raise

    def _format_page_info(self, metadata: dict) -> str:
        """메타데이터에서 페이지 정보 포맷팅"""
        node_type = metadata.get("node_type", "unknown")

        if node_type in ["intro", "end"]:
            return f"{metadata.get('start_page', '?')}-{metadata.get('end_page', '?')}"
        elif node_type == "chapter":
            return f"{metadata.get('start_page', '?')}-{metadata.get('end_page', '?')}"
        else:
            return f"{metadata.get('page', '?')}"


# =============================================================================
# 편의 함수
# =============================================================================


def create_summary_chain(model: str = None, temperature: float = None) -> SummaryChain:
    """
    요약 체인 생성 편의 함수

    Args:
        model: OpenAI 모델 이름
        temperature: 생성 온도

    Returns:
        SummaryChain 인스턴스
    """
    return SummaryChain(model=model, temperature=temperature)


def summarize_document(
    document: Document, model: str = None, temperature: float = None
) -> NodeSummary:
    """
    단일 Document 요약 편의 함수

    Args:
        document: Document 객체
        model: OpenAI 모델 이름
        temperature: 생성 온도

    Returns:
        NodeSummary 객체
    """
    chain = create_summary_chain(model=model, temperature=temperature)
    return chain.summarize(document)
````

## File: backend/summarizers/node_summarizer.py
````python
"""
Books Assistant - 노드 요약 Runnable
전체 Document 요약 파이프라인 (LCEL 활용)
"""

from typing import List, Dict, Any, Optional
from pathlib import Path
import json
import logging
from datetime import datetime

from langchain_core.documents import Document
from langchain_core.runnables import RunnablePassthrough, RunnableLambda

from backend.summarizers.document_loaders import load_book_documents
from backend.summarizers.llm_chains import SummaryChain, NodeSummary

logger = logging.getLogger(__name__)


class NodeSummarizer:
    """
    노드 요약 Runnable
    
    Document 로드 → 요약 생성 → 저장 전체 파이프라인
    """
    
    def __init__(
        self,
        parsing_result_path: str = "output/tests/parsing_result_clean.json",
        structure_result_path: str = "output/tests/structure_result.json",
        output_dir: str = "output/summaries"
    ):
        """
        초기화
        
        Args:
            parsing_result_path: 파싱 결과 경로
            structure_result_path: 구조 분석 결과 경로
            output_dir: 요약 저장 디렉토리
        """
        self.parsing_result_path = parsing_result_path
        self.structure_result_path = structure_result_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # LLM 체인 초기화
        self.summary_chain = SummaryChain()
        
        logger.info(f"NodeSummarizer initialized")
        logger.info(f"  Output directory: {self.output_dir}")
        logger.info(f"  Model: {self.summary_chain.model_name}")
    
    def load_documents(self) -> List[Document]:
        """Document 로드"""
        logger.info("Loading documents...")
        documents = load_book_documents(
            parsing_result_path=self.parsing_result_path,
            structure_result_path=self.structure_result_path,
            lazy=False
        )
        logger.info(f"✓ Loaded {len(documents)} documents")
        return documents
    
    def summarize_documents(
        self,
        documents: List[Document],
        use_batch: bool = True
    ) -> List[NodeSummary]:
        """
        Document 리스트 요약
        
        Args:
            documents: Document 리스트
            use_batch: 배치 처리 여부
        
        Returns:
            NodeSummary 리스트
        """
        logger.info(f"Summarizing {len(documents)} documents...")
        logger.info(f"  Batch mode: {use_batch}")
        
        if use_batch:
            # 배치 처리
            summaries = self.summary_chain.batch_summarize(documents)
        else:
            # 순차 처리 (진행 상황 표시)
            summaries = []
            for i, doc in enumerate(documents, 1):
                logger.info(f"  Processing {i}/{len(documents)}: {doc.metadata['node_id']}")
                summary = self.summary_chain.summarize(doc)
                summaries.append(summary)
        
        logger.info(f"✓ Summarization completed: {len(summaries)} summaries")
        return summaries
    
    def save_summaries(
        self,
        summaries: List[NodeSummary],
        filename: str = "book_summaries.json"
    ) -> Path:
        """
        요약 결과 저장
        
        Args:
            summaries: NodeSummary 리스트
            filename: 저장 파일명
        
        Returns:
            저장된 파일 경로
        """
        output_file = self.output_dir / filename
        
        # Pydantic 모델을 dict로 변환
        summaries_dict = [summary.model_dump() for summary in summaries]
        
        # 메타데이터 추가
        output_data = {
            "generated_at": datetime.now().isoformat(),
            "model": self.summary_chain.model_name,
            "temperature": self.summary_chain.temperature,
            "total_summaries": len(summaries),
            "summaries": summaries_dict
        }
        
        # JSON 저장
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ Summaries saved to {output_file}")
        return output_file
    
    def summarize_all(
        self,
        use_batch: bool = True,
        save: bool = True,
        filename: str = "book_summaries.json"
    ) -> Dict[str, Any]:
        """
        전체 파이프라인 실행
        
        Args:
            use_batch: 배치 처리 여부
            save: 결과 저장 여부
            filename: 저장 파일명
        
        Returns:
            {
                "documents": List[Document],
                "summaries": List[NodeSummary],
                "output_file": Path (if save=True)
            }
        """
        logger.info("=" * 80)
        logger.info("Starting full summarization pipeline...")
        logger.info("=" * 80)
        
        # 1. Document 로드
        documents = self.load_documents()
        
        # 2. 요약 생성
        summaries = self.summarize_documents(documents, use_batch=use_batch)
        
        result = {
            "documents": documents,
            "summaries": summaries
        }
        
        # 3. 저장 (옵션)
        if save:
            output_file = self.save_summaries(summaries, filename)
            result["output_file"] = output_file
        
        logger.info("=" * 80)
        logger.info("✓ Full pipeline completed!")
        logger.info(f"  Documents: {len(documents)}")
        logger.info(f"  Summaries: {len(summaries)}")
        if save:
            logger.info(f"  Saved to: {result['output_file']}")
        logger.info("=" * 80)
        
        return result
    
    def get_summary_statistics(
        self,
        summaries: List[NodeSummary]
    ) -> Dict[str, Any]:
        """
        요약 통계 생성
        
        Args:
            summaries: NodeSummary 리스트
        
        Returns:
            통계 정보
        """
        stats = {
            "total_summaries": len(summaries),
            "avg_facts": sum(len(s.facts) for s in summaries) / len(summaries),
            "avg_claims": sum(len(s.claims) for s in summaries) / len(summaries),
            "avg_examples": sum(len(s.examples) for s in summaries) / len(summaries),
            "avg_quotes": sum(len(s.quotes) for s in summaries) / len(summaries),
            "avg_keywords": sum(len(s.keywords) for s in summaries) / len(summaries),
            "avg_summary_length": sum(len(s.summary) for s in summaries) / len(summaries),
            "node_types": {}
        }
        
        # 노드 타입별 통계
        for summary in summaries:
            # node_id에서 타입 추론 (예: "intro", "ch1", "end")
            node_id = summary.node_id
            if node_id == "intro":
                node_type = "intro"
            elif node_id == "end":
                node_type = "end"
            elif node_id.startswith("ch"):
                node_type = "chapter"
            else:
                node_type = "unknown"
            
            stats["node_types"][node_type] = stats["node_types"].get(node_type, 0) + 1
        
        return stats


# =============================================================================
# LCEL Runnable 구성 (선택적)
# =============================================================================

def create_node_summary_runnable(
    summary_chain: SummaryChain
) -> RunnableLambda:
    """
    LCEL 기반 노드 요약 Runnable 생성
    
    Args:
        summary_chain: SummaryChain 인스턴스
    
    Returns:
        Runnable 체인
    """
    def format_node_input(doc: Document) -> Dict[str, Any]:
        """Document를 체인 입력 형식으로 변환"""
        metadata = doc.metadata
        page_info = _format_page_info(metadata)
        
        return {
            "node_id": metadata.get("node_id", "unknown"),
            "node_type": metadata.get("node_type", "unknown"),
            "page_info": page_info,
            "content": doc.page_content
        }
    
    def _format_page_info(metadata: dict) -> str:
        """페이지 정보 포맷팅"""
        node_type = metadata.get("node_type", "unknown")
        
        if node_type in ["intro", "end"]:
            return f"{metadata.get('start_page', '?')}-{metadata.get('end_page', '?')}"
        elif node_type == "chapter":
            return f"{metadata.get('start_page', '?')}-{metadata.get('end_page', '?')}"
        else:
            return f"{metadata.get('page', '?')}"
    
    # LCEL 체인 구성
    node_summary_chain = (
        RunnablePassthrough.assign(formatted=RunnableLambda(format_node_input))
        | summary_chain.chain
    )
    
    return node_summary_chain


# =============================================================================
# 편의 함수
# =============================================================================

def summarize_book(
    parsing_result_path: str = "output/tests/parsing_result_clean.json",
    structure_result_path: str = "output/tests/structure_result.json",
    output_dir: str = "output/summaries",
    use_batch: bool = True,
    save: bool = True
) -> Dict[str, Any]:
    """
    책 전체 요약 편의 함수
    
    Args:
        parsing_result_path: 파싱 결과 경로
        structure_result_path: 구조 분석 결과 경로
        output_dir: 출력 디렉토리
        use_batch: 배치 처리 여부
        save: 저장 여부
    
    Returns:
        요약 결과
    """
    summarizer = NodeSummarizer(
        parsing_result_path=parsing_result_path,
        structure_result_path=structure_result_path,
        output_dir=output_dir
    )
    
    return summarizer.summarize_all(use_batch=use_batch, save=save)
````

## File: backend/summarizers/page_splitter.py
````python
"""
Books Assistant - 페이지 분할기
챕터 Document를 페이지별 Document로 분할
"""

from typing import List, Dict, Any
import json
import logging
from pathlib import Path

from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class PageSplitter:
    """챕터 Document를 페이지별 Document로 분할"""

    def __init__(
        self, parsing_result_path: str = "output/tests/parsing_result_clean.json"
    ):
        """
        초기화

        Args:
            parsing_result_path: 파싱 결과 JSON 경로
        """
        self.parsing_result_path = Path(parsing_result_path)
        self.page_elements: Dict[int, List[Dict[str, Any]]] = {}

        self._load_parsing_data()

    def _load_parsing_data(self) -> None:
        """파싱 결과 로드 및 인덱싱"""
        logger.info(f"Loading parsing data from {self.parsing_result_path}")

        with open(self.parsing_result_path, "r", encoding="utf-8") as f:
            parsing_data = json.load(f)

        # 페이지별 element 인덱싱
        if parsing_data and parsing_data.get("success"):
            for page_data in parsing_data.get("pages", []):
                page_num = page_data.get("page_number")
                self.page_elements[page_num] = page_data.get("elements", [])

        logger.info(f"✓ Indexed {len(self.page_elements)} pages")

    def split_chapter_to_pages(
        self, chapter_doc: Document, filter_categories: List[str] = None
    ) -> List[Document]:
        """
        챕터 Document를 페이지별 Document로 분할

        Args:
            chapter_doc: 챕터 Document
            filter_categories: 포함할 element 카테고리

        Returns:
            페이지별 Document 리스트
        """
        metadata = chapter_doc.metadata
        chapter_id = metadata.get("chapter_id")
        start_page = metadata.get("start_page")
        end_page = metadata.get("end_page")

        if not all([chapter_id, start_page, end_page]):
            logger.error(f"Invalid chapter metadata: {metadata}")
            return []

        # 기본 카테고리 필터
        if filter_categories is None:
            filter_categories = ["paragraph", "heading1", "heading2", "heading3"]

        page_documents = []

        for page_num in range(start_page, end_page + 1):
            # 페이지 텍스트 추출
            page_text = self._extract_page_text(page_num, filter_categories)

            if not page_text:
                logger.warning(f"No text found for page {page_num}")
                continue

            # 페이지 Document 생성
            page_doc = Document(
                page_content=page_text,
                metadata={
                    "page": page_num,
                    "chapter_id": chapter_id,
                    "chapter_number": metadata.get("chapter_number"),
                    "chapter_title": metadata.get("chapter_title"),
                    "node_type": "page",
                    "level": 1,  # 페이지는 레벨 1
                },
            )

            page_documents.append(page_doc)

        logger.info(
            f"✓ Split chapter {chapter_id} into {len(page_documents)} pages "
            f"({start_page}-{end_page})"
        )

        return page_documents

    def _extract_page_text(self, page_num: int, filter_categories: List[str]) -> str:
        """페이지에서 텍스트 추출"""
        if page_num not in self.page_elements:
            return ""

        elements = self.page_elements[page_num]
        texts = []

        for element in elements:
            # 카테고리 필터링
            if element.get("category") not in filter_categories:
                continue

            text = element.get("text", "").strip()
            if text:
                texts.append(text)

        return "\n".join(texts)

    def get_page_count(self, chapter_doc: Document) -> int:
        """챕터의 페이지 수 반환"""
        metadata = chapter_doc.metadata
        start_page = metadata.get("start_page", 0)
        end_page = metadata.get("end_page", 0)

        return end_page - start_page + 1
````

## File: backend/summarizers/page_summarizer.py
````python
"""
Books Assistant - 페이지 요약기
페이지별 Document를 요약하고 캐싱
"""

from typing import List
import logging

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from backend.summarizers.page_summary_cache import PageSummary, PageSummaryCache
from backend.config.settings import settings

logger = logging.getLogger(__name__)


# =============================================================================
# 프롬프트
# =============================================================================

PAGE_SUMMARY_PROMPT = """당신은 책의 페이지를 요약하는 전문가입니다.

주어진 페이지 내용을 읽고 핵심 정보를 추출하세요.

## 페이지 정보
- 챕터: {chapter_title}
- 페이지: {page}

## 페이지 내용
{content}

## 요약 지침

1. **Facts (핵심 사실)**
   - 이 페이지에서 언급된 중요한 사실들
   - 최대 5개
   - 구체적이고 명확하게

2. **Summary (페이지 요약)**
   - 이 페이지의 핵심 내용을 30-100자로 요약
   - 다음 페이지와 연결될 수 있도록 맥락 포함

## 주의사항
- 원문의 의미를 왜곡하지 마세요
- 페이지 범위 내의 내용만 다루세요
- 중요도 순으로 정렬하세요
"""


# =============================================================================
# 페이지 요약기
# =============================================================================


class PageSummarizer:
    """페이지 요약 생성 및 캐싱"""

    def __init__(
        self, model: str = None, temperature: float = None, enable_cache: bool = True
    ):
        """
        초기화

        Args:
            model: OpenAI 모델 이름
            temperature: 생성 온도
            enable_cache: 캐싱 활성화 여부
        """
        self.model_name = model or settings.openai_model
        self.temperature = (
            temperature if temperature is not None else settings.openai_temperature
        )

        # LLM 초기화
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            api_key=settings.openai_api_key,
        ).with_structured_output(PageSummary)

        # 프롬프트
        self.prompt = ChatPromptTemplate.from_template(PAGE_SUMMARY_PROMPT)

        # 체인 구성
        self.chain = self.prompt | self.llm

        # 캐시
        self.cache = PageSummaryCache() if enable_cache else None

        logger.info(
            f"PageSummarizer initialized: model={self.model_name}, cache={enable_cache}"
        )

    def summarize_page(self, page_doc: Document, use_cache: bool = True) -> PageSummary:
        """
        단일 페이지 요약

        Args:
            page_doc: 페이지 Document
            use_cache: 캐시 사용 여부

        Returns:
            PageSummary 객체
        """
        metadata = page_doc.metadata
        page_num = metadata.get("page")
        chapter_id = metadata.get("chapter_id")
        chapter_title = metadata.get("chapter_title", "")
        content = page_doc.page_content

        # content hash 생성
        content_hash = self.cache.get_content_hash(content) if self.cache else None

        # 캐시 확인
        if use_cache and self.cache:
            cached_summary = self.cache.get_cached_summary(
                chapter_id, page_num, content_hash
            )
            if cached_summary:
                return cached_summary

        # LLM 호출
        logger.info(f"Summarizing page {page_num} of {chapter_id}...")

        try:
            # 입력 데이터 준비
            input_data = {
                "chapter_title": chapter_title,
                "page": page_num,
                "content": content,
            }

            # LLM 호출
            summary = self.chain.invoke(input_data)

            # content_hash 추가
            summary.content_hash = content_hash

            # 캐시 저장
            if use_cache and self.cache:
                self.cache.save_cache(summary)

            logger.info(f"✓ Page {page_num} summarized")
            return summary

        except Exception as e:
            logger.error(f"Error summarizing page {page_num}: {e}")
            raise

    def summarize_pages(
        self, page_docs: List[Document], use_cache: bool = True, use_batch: bool = False
    ) -> List[PageSummary]:
        """
        여러 페이지 요약

        Args:
            page_docs: 페이지 Document 리스트
            use_cache: 캐시 사용 여부
            use_batch: 배치 처리 여부 (현재 미지원, 캐싱이 더 효율적)

        Returns:
            PageSummary 리스트
        """
        summaries = []

        for i, page_doc in enumerate(page_docs, 1):
            logger.info(f"Processing page {i}/{len(page_docs)}...")
            summary = self.summarize_page(page_doc, use_cache=use_cache)
            summaries.append(summary)

        logger.info(f"✓ Summarized {len(summaries)} pages")
        return summaries
````

## File: backend/summarizers/page_summary_cache.py
````python
"""
Books Assistant - 페이지 요약 캐시
페이지별 요약 결과를 캐싱하여 API 비용 절감
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic 모델
# =============================================================================


class PageSummary(BaseModel):
    """페이지 요약 구조체"""

    page: int = Field(description="페이지 번호")
    chapter_id: str = Field(description="챕터 ID")

    facts: list[str] = Field(
        description="핵심 사실들 (최대 5개)", max_length=5, default_factory=list
    )

    summary: str = Field(
        description="페이지 요약 (50-100자)", min_length=30, max_length=200
    )

    content_hash: str = Field(description="내용 해시 (캐시 검증용)")


# =============================================================================
# 캐시 매니저
# =============================================================================


class PageSummaryCache:
    """페이지 요약 캐시 관리자"""

    def __init__(self, cache_dir: str = "cache/summaries"):
        """
        초기화

        Args:
            cache_dir: 캐시 디렉토리 경로
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"PageSummaryCache initialized: {self.cache_dir}")

    def get_cache_key(self, chapter_id: str, page_num: int) -> str:
        """
        캐시 키 생성

        Args:
            chapter_id: 챕터 ID
            page_num: 페이지 번호

        Returns:
            캐시 파일명
        """
        return f"{chapter_id}_page{page_num}.json"

    def get_content_hash(self, content: str) -> str:
        """
        컨텐츠 해시 생성

        Args:
            content: 페이지 텍스트

        Returns:
            MD5 해시
        """
        return hashlib.md5(content.encode("utf-8")).hexdigest()

    def get_cached_summary(
        self, chapter_id: str, page_num: int, content_hash: Optional[str] = None
    ) -> Optional[PageSummary]:
        """
        캐시된 요약 조회

        Args:
            chapter_id: 챕터 ID
            page_num: 페이지 번호
            content_hash: 내용 해시 (검증용, optional)

        Returns:
            PageSummary 또는 None
        """
        cache_key = self.get_cache_key(chapter_id, page_num)
        cache_file = self.cache_dir / cache_key

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # PageSummary 객체로 변환
            summary = PageSummary(**data["summary"])

            # content_hash 검증 (제공된 경우)
            if content_hash and summary.content_hash != content_hash:
                logger.warning(
                    f"Cache hash mismatch for {chapter_id} page {page_num}, "
                    f"invalidating cache"
                )
                return None

            logger.info(f"✓ Cache hit: {cache_key}")
            return summary

        except Exception as e:
            logger.error(f"Error loading cache {cache_key}: {e}")
            return None

    def save_cache(self, summary: PageSummary) -> Path:
        """
        요약 결과를 캐시에 저장

        Args:
            summary: PageSummary 객체

        Returns:
            저장된 파일 경로
        """
        cache_key = self.get_cache_key(summary.chapter_id, summary.page)
        cache_file = self.cache_dir / cache_key

        # 메타데이터 포함하여 저장
        cache_data = {
            "summary": summary.model_dump(),
            "cached_at": datetime.now().isoformat(),
            "chapter_id": summary.chapter_id,
            "page": summary.page,
        }

        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✓ Cache saved: {cache_key}")
        return cache_file

    def clear_cache(self, chapter_id: Optional[str] = None) -> int:
        """
        캐시 삭제

        Args:
            chapter_id: 특정 챕터만 삭제 (None이면 전체 삭제)

        Returns:
            삭제된 파일 수
        """
        if chapter_id:
            pattern = f"{chapter_id}_page*.json"
        else:
            pattern = "*.json"

        deleted = 0
        for cache_file in self.cache_dir.glob(pattern):
            cache_file.unlink()
            deleted += 1

        logger.info(f"✓ Cleared {deleted} cache files")
        return deleted

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        캐시 통계 반환

        Returns:
            캐시 통계 정보
        """
        cache_files = list(self.cache_dir.glob("*.json"))

        stats = {
            "total_cached_pages": len(cache_files),
            "cache_dir": str(self.cache_dir),
            "chapters": {},
        }

        # 챕터별 통계
        for cache_file in cache_files:
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                chapter_id = data.get("chapter_id", "unknown")
                stats["chapters"][chapter_id] = stats["chapters"].get(chapter_id, 0) + 1
            except Exception:
                continue

        return stats
````

## File: backend/utils/convert_gt_csv_to_json.py
````python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ground Truth CSV를 JSON으로 변환

CSV 형식:
,세부,시작페이지,종료페이지
start,start,1,26
main,ch1,27,70
,ch2,71,108
...
end,end,375,418
"""

import csv
import json
from pathlib import Path


def convert_csv_to_json(csv_path: str, output_path: str) -> None:
    """CSV GT를 JSON 형식으로 변환"""
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:  # BOM 처리
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # 구조 초기화
    structure = {
        "start": {"pages": [], "page_count": 0, "label": "서문 (표지 + 전문)"},
        "main": {"pages": [], "page_count": 0, "label": "본문", "chapters": []},
        "end": {"pages": [], "page_count": 0, "label": "종문 (맺음말 + 부록)"}
    }
    
    current_section = None
    
    for row in rows:
        # 첫 번째 컬럼 (빈 문자열일 수 있음)
        first_col = list(row.keys())[0]
        section = row[first_col].strip() if row[first_col] else current_section
        detail = row['세부'].strip()
        start_page = int(row['시작페이지'])
        end_page = int(row['종료페이지'])
        
        if section:
            current_section = section
        
        # 페이지 범위 생성
        pages = list(range(start_page, end_page + 1))
        page_count = len(pages)
        
        if current_section == 'start':
            structure['start']['pages'] = pages
            structure['start']['page_count'] = page_count
            
        elif current_section == 'main':
            if detail.startswith('ch'):
                chapter_num = int(detail[2:])
                structure['main']['chapters'].append({
                    "number": chapter_num,
                    "start_page": start_page,
                    "end_page": end_page,
                    "page_count": page_count,
                    "label": f"제{chapter_num}장"
                })
            
            # 본문 전체 페이지는 모든 챕터를 합쳐서 계산
            if not structure['main']['pages']:
                structure['main']['pages'] = pages
            else:
                structure['main']['pages'].extend(pages)
            
        elif current_section == 'end':
            structure['end']['pages'] = pages
            structure['end']['page_count'] = page_count
    
    # 본문 페이지 중복 제거 및 정렬
    structure['main']['pages'] = sorted(list(set(structure['main']['pages'])))
    structure['main']['page_count'] = len(structure['main']['pages'])
    
    # 전체 페이지 수 계산
    total_pages = max(structure['end']['pages']) if structure['end']['pages'] else 0
    
    # 최종 JSON 생성
    ground_truth = {
        "pdf_name": "지능의 탄생.pdf",
        "description": "구조 분석 정확도 검증용 Ground Truth (용어: 서문/본문/종문)",
        "total_pages_after_split": total_pages,
        "structure": structure,
        "summary": {
            "start_pages": structure['start']['page_count'],
            "main_pages": structure['main']['page_count'],
            "end_pages": structure['end']['page_count'],
            "chapter_count": len(structure['main']['chapters'])
        }
    }
    
    # JSON 저장
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(ground_truth, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Ground Truth JSON 생성 완료: {output_path}")
    print(f"   총 페이지: {total_pages}")
    print(f"   서문: {structure['start']['page_count']}p")
    print(f"   본문: {structure['main']['page_count']}p ({len(structure['main']['chapters'])} 챕터)")
    print(f"   종문: {structure['end']['page_count']}p")


if __name__ == "__main__":
    csv_path = "docs/지능의 탄생_GT.csv"
    output_path = "backend/tests/ground_truth.json"
    
    convert_csv_to_json(csv_path, output_path)
````
