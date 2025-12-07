"""
챕터 서머리 재처리 스크립트

개선된 프롬프트로 챕터 서머리를 재생성합니다.
- 페이지 엔티티는 DB에서 읽어오므로 재생성 불필요
- 2페이지 이하 챕터는 자동으로 스킵됨
"""
import logging
import sys
from sqlalchemy.orm import Session
from backend.api.database import SessionLocal
from backend.api.models.book import Book
from backend.api.services.extraction_service import ExtractionService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def reprocess_chapter_summaries(book_id: int) -> None:
    """
    특정 책의 챕터 서머리 재처리
    
    Args:
        book_id: 책 ID
    """
    db: Session = SessionLocal()
    
    try:
        # 책 조회
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            logger.error(f"[ERROR] Book {book_id} not found")
            return
        
        # 페이지 엔티티가 있는지 확인
        from backend.api.models.book import PageSummary
        page_count = db.query(PageSummary).filter(
            PageSummary.book_id == book_id
        ).count()
        
        if page_count == 0:
            logger.error(
                f"[ERROR] Book {book_id} has no page entities. "
                f"Please run extract_pages first."
            )
            return
        
        logger.info(
            f"[INFO] Reprocessing chapter summaries for book {book_id} "
            f"({book.title or 'Unknown'})"
        )
        logger.info(f"[INFO] Found {page_count} page entities in DB")
        
        # ExtractionService 초기화 및 챕터 구조화 실행
        service = ExtractionService(db)
        result_book = service.extract_chapters(book_id)
        
        logger.info(
            f"[INFO] Chapter summarization completed for book {book_id}. "
            f"Status: {result_book.status}"
        )
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to reprocess chapter summaries: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python reprocess_chapter_summaries.py <book_id>")
        print("Example: python reprocess_chapter_summaries.py 176")
        sys.exit(1)
    
    book_id = int(sys.argv[1])
    reprocess_chapter_summaries(book_id)

