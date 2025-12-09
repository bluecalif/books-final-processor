"""책 관련 데이터 모델"""
from enum import Enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from backend.api.database import Base


class BookStatus(str, Enum):
    """책 처리 상태 Enum"""
    UPLOADED = "uploaded"
    PARSED = "parsed"
    STRUCTURED = "structured"
    PAGE_SUMMARIZED = "page_summarized"
    SUMMARIZED = "summarized"
    ERROR_PARSING = "error_parsing"
    ERROR_STRUCTURING = "error_structuring"
    ERROR_SUMMARIZING = "error_summarizing"
    FAILED = "failed"


class Book(Base):
    """책 테이블"""
    __tablename__ = "books"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    author = Column(String, nullable=True)
    category = Column(String, nullable=True)  # 분야 (예: 역사/사회, 경제/경영 등)
    source_file_path = Column(String, nullable=False)
    page_count = Column(Integer, nullable=True)
    status = Column(SQLEnum(BookStatus), default=BookStatus.UPLOADED, nullable=False, index=True)  # 인덱스 추가 (get_books 필터 최적화)
    structure_data = Column(JSON, nullable=True)  # 최종 확정된 구조
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 관계
    pages = relationship("Page", back_populates="book", cascade="all, delete-orphan")
    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan")
    page_summaries = relationship("PageSummary", back_populates="book", cascade="all, delete-orphan")
    chapter_summaries = relationship("ChapterSummary", back_populates="book", cascade="all, delete-orphan")


class Page(Base):
    """페이지 테이블"""
    __tablename__ = "pages"
    
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)  # 1-based
    raw_text = Column(Text, nullable=True)
    page_metadata = Column(JSON, nullable=True)  # 레이아웃/블록 정보
    
    # 관계
    book = relationship("Book", back_populates="pages")
    summary = relationship("PageSummary", back_populates="page", uselist=False)


class Chapter(Base):
    """챕터 테이블"""
    __tablename__ = "chapters"
    
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    order_index = Column(Integer, nullable=False)  # 0-based
    start_page = Column(Integer, nullable=False)
    end_page = Column(Integer, nullable=False)
    section_type = Column(String, nullable=True)  # 본문/서문/부록
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 관계
    book = relationship("Book", back_populates="chapters")
    summary = relationship("ChapterSummary", back_populates="chapter", uselist=False)


class PageSummary(Base):
    """페이지 요약 테이블"""
    __tablename__ = "page_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    page_id = Column(Integer, ForeignKey("pages.id", ondelete="CASCADE"), nullable=True)
    page_number = Column(Integer, nullable=False)  # 중복 저장 (조회 편의)
    summary_text = Column(Text, nullable=False)
    structured_data = Column(JSON, nullable=True)  # 구조화된 엔티티 데이터 (도메인별 스키마)
    lang = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 관계
    book = relationship("Book", back_populates="page_summaries")
    page = relationship("Page", back_populates="summary")


class ChapterSummary(Base):
    """챕터 요약 테이블"""
    __tablename__ = "chapter_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id = Column(Integer, ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    summary_text = Column(Text, nullable=False)
    structured_data = Column(JSON, nullable=True)  # 구조화된 엔티티 데이터 (도메인별 스키마)
    lang = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 관계
    book = relationship("Book", back_populates="chapter_summaries")
    chapter = relationship("Chapter", back_populates="summary")

