"""엔티티 추출 관련 API 라우터"""
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List

from backend.api.database import get_db
from backend.api.services.extraction_service import ExtractionService
from backend.api.schemas.book import PageSummaryResponse, ChapterSummaryResponse
from backend.api.models.book import Book, BookStatus, PageSummary, ChapterSummary, Chapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/books", tags=["extraction"])


def _extract_pages_background(book_id: int):
    """
    백그라운드에서 페이지 엔티티 추출 실행
    
    Args:
        book_id: 책 ID
    """
    logger.info(f"[INFO] Starting background page extraction for book_id={book_id}")
    
    # 새로운 DB 세션 생성 (백그라운드 작업용)
    db = next(get_db())
    
    try:
        extraction_service = ExtractionService(db)
        book = extraction_service.extract_pages(book_id)
        logger.info(
            f"[INFO] Background page extraction completed: book_id={book_id}, "
            f"status={book.status}"
        )
    except Exception as e:
        logger.error(f"[ERROR] Background page extraction failed: book_id={book_id}, error={e}")
        # 에러 발생 시 상태 업데이트 (선택적)
        try:
            book = db.query(Book).filter(Book.id == book_id).first()
            if book:
                book.status = BookStatus.ERROR_SUMMARIZING
                db.commit()
        except Exception as update_error:
            logger.error(f"[ERROR] Failed to update book status: {update_error}")
    finally:
        db.close()


def _extract_chapters_background(book_id: int):
    """
    백그라운드에서 챕터 구조화 실행
    
    Args:
        book_id: 책 ID
    """
    logger.info(f"[INFO] Starting background chapter structuring for book_id={book_id}")
    
    # 새로운 DB 세션 생성 (백그라운드 작업용)
    db = next(get_db())
    
    try:
        extraction_service = ExtractionService(db)
        book = extraction_service.extract_chapters(book_id)
        logger.info(
            f"[INFO] Background chapter structuring completed: book_id={book_id}, "
            f"status={book.status}"
        )
    except Exception as e:
        logger.error(f"[ERROR] Background chapter structuring failed: book_id={book_id}, error={e}")
        # 에러 발생 시 상태 업데이트 (선택적)
        try:
            book = db.query(Book).filter(Book.id == book_id).first()
            if book:
                book.status = BookStatus.ERROR_SUMMARIZING
                db.commit()
        except Exception as update_error:
            logger.error(f"[ERROR] Failed to update book status: {update_error}")
    finally:
        db.close()


@router.get("/{book_id}/pages", response_model=List[PageSummaryResponse])
def get_page_entities(book_id: int, db: Session = Depends(get_db)):
    """
    페이지별 엔티티 리스트 조회
    
    Args:
        book_id: 책 ID
        db: 데이터베이스 세션
    
    Returns:
        페이지 엔티티 리스트
    """
    # 책 존재 확인
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
    
    # 페이지 엔티티 조회
    page_summaries = (
        db.query(PageSummary)
        .filter(PageSummary.book_id == book_id)
        .order_by(PageSummary.page_number)
        .all()
    )
    
    return page_summaries


@router.get("/{book_id}/pages/{page_number}", response_model=PageSummaryResponse)
def get_page_entity(book_id: int, page_number: int, db: Session = Depends(get_db)):
    """
    페이지 엔티티 상세 조회
    
    Args:
        book_id: 책 ID
        page_number: 페이지 번호
        db: 데이터베이스 세션
    
    Returns:
        페이지 엔티티 상세
    """
    # 책 존재 확인
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
    
    # 페이지 엔티티 조회
    page_summary = (
        db.query(PageSummary)
        .filter(
            PageSummary.book_id == book_id,
            PageSummary.page_number == page_number,
        )
        .first()
    )
    
    if not page_summary:
        raise HTTPException(
            status_code=404,
            detail=f"Page {page_number} entity not found for book {book_id}",
        )
    
    return page_summary


@router.get("/{book_id}/chapters", response_model=List[ChapterSummaryResponse])
def get_chapter_entities(book_id: int, db: Session = Depends(get_db)):
    """
    챕터별 구조화 결과 리스트 조회
    
    Args:
        book_id: 책 ID
        db: 데이터베이스 세션
    
    Returns:
        챕터 구조화 결과 리스트
    """
    # 책 존재 확인
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
    
    # 챕터 구조화 결과 조회
    chapter_summaries = (
        db.query(ChapterSummary)
        .filter(ChapterSummary.book_id == book_id)
        .join(Chapter, ChapterSummary.chapter_id == Chapter.id)
        .order_by(Chapter.order_index)
        .all()
    )
    
    return chapter_summaries


@router.get("/{book_id}/chapters/{chapter_id}", response_model=ChapterSummaryResponse)
def get_chapter_entity(book_id: int, chapter_id: int, db: Session = Depends(get_db)):
    """
    챕터 구조화 결과 상세 조회
    
    Args:
        book_id: 책 ID
        chapter_id: 챕터 ID
        db: 데이터베이스 세션
    
    Returns:
        챕터 구조화 결과 상세
    """
    # 책 존재 확인
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
    
    # 챕터 존재 확인
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id, Chapter.book_id == book_id).first()
    if not chapter:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter {chapter_id} not found for book {book_id}",
        )
    
    # 챕터 구조화 결과 조회
    chapter_summary = (
        db.query(ChapterSummary)
        .filter(ChapterSummary.chapter_id == chapter_id)
        .first()
    )
    
    if not chapter_summary:
        raise HTTPException(
            status_code=404,
            detail=f"Chapter {chapter_id} entity not found for book {book_id}",
        )
    
    return chapter_summary


@router.post("/{book_id}/extract/pages")
def start_page_extraction(
    book_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    페이지 엔티티 추출 시작 (백그라운드 작업)
    
    Args:
        book_id: 책 ID
        background_tasks: FastAPI 백그라운드 작업
        db: 데이터베이스 세션
    
    Returns:
        작업 시작 메시지
    """
    # 책 존재 확인
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
    
    # 구조 분석 완료 확인
    if not book.structure_data:
        raise HTTPException(
            status_code=400,
            detail=f"Book {book_id} has no structure_data. Please run structure analysis first.",
        )
    
    # 백그라운드 작업 추가
    background_tasks.add_task(_extract_pages_background, book_id)
    
    logger.info(f"[INFO] Page extraction task queued for book_id={book_id}")
    
    return {
        "message": "Page extraction started",
        "book_id": book_id,
        "status": "processing",
    }


@router.post("/{book_id}/extract/chapters")
def start_chapter_extraction(
    book_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    챕터 구조화 시작 (백그라운드 작업)
    
    Args:
        book_id: 책 ID
        background_tasks: FastAPI 백그라운드 작업
        db: 데이터베이스 세션
    
    Returns:
        작업 시작 메시지
    """
    # 책 존재 확인
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
    
    # 페이지 엔티티 추출 완료 확인
    if book.status != BookStatus.PAGE_SUMMARIZED:
        raise HTTPException(
            status_code=400,
            detail=f"Book {book_id} is not in page_summarized status. Current status: {book.status}",
        )
    
    # 백그라운드 작업 추가
    background_tasks.add_task(_extract_chapters_background, book_id)
    
    logger.info(f"[INFO] Chapter extraction task queued for book_id={book_id}")
    
    return {
        "message": "Chapter extraction started",
        "book_id": book_id,
        "status": "processing",
    }

