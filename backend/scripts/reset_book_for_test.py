"""
테스트를 위해 특정 도서의 요약 데이터를 초기화하는 스크립트

PageSummary, ChapterSummary를 삭제하고 상태를 'structured'로 되돌립니다.
"""
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.api.models.book import Book, BookStatus, PageSummary, ChapterSummary
from backend.api.database import SessionLocal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reset_book(book_id: int):
    """
    특정 도서의 요약 데이터를 초기화
    
    Args:
        book_id: 책 ID
    """
    db = SessionLocal()
    
    try:
        # 책 조회
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            logger.error(f"[ERROR] Book {book_id} not found")
            return
        
        logger.info(f"[INFO] Resetting book: ID={book_id}, Title={book.title}, Current Status={book.status}")
        
        # PageSummary 삭제
        page_summaries = db.query(PageSummary).filter(PageSummary.book_id == book_id).all()
        if page_summaries:
            count = len(page_summaries)
            for ps in page_summaries:
                db.delete(ps)
            logger.info(f"[INFO] Deleted {count} PageSummaries")
        else:
            logger.info(f"[INFO] No PageSummaries to delete")
        
        # ChapterSummary 삭제
        chapter_summaries = db.query(ChapterSummary).filter(ChapterSummary.book_id == book_id).all()
        if chapter_summaries:
            count = len(chapter_summaries)
            for cs in chapter_summaries:
                db.delete(cs)
            logger.info(f"[INFO] Deleted {count} ChapterSummaries")
        else:
            logger.info(f"[INFO] No ChapterSummaries to delete")
        
        # 상태를 structured로 되돌림
        old_status = book.status
        book.status = BookStatus.STRUCTURED
        
        db.commit()
        
        logger.info(f"[INFO] Book status changed: {old_status} -> {book.status}")
        logger.info(f"[SUCCESS] Book {book_id} reset completed")
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to reset book {book_id}: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        logger.error("[ERROR] Usage: python -m backend.scripts.reset_book_for_test <book_id>")
        logger.info("[INFO] Example: python -m backend.scripts.reset_book_for_test 176")
        sys.exit(1)
    
    book_id = int(sys.argv[1])
    logger.info(f"[INFO] Starting reset for book_id={book_id}...")
    reset_book(book_id)

