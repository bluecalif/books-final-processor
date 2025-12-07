"""
챕터 서머리 캐시만 삭제하는 스크립트

페이지 엔티티 캐시는 유지하고, 챕터 서머리 캐시만 삭제하여 재처리 가능하게 합니다.
"""
import logging
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session
from backend.api.database import SessionLocal
from backend.api.models.book import Book
from backend.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def delete_chapter_caches(book_id: Optional[int] = None) -> None:
    """
    챕터 서머리 캐시만 삭제 (페이지 엔티티 캐시는 유지)
    
    Args:
        book_id: 특정 책 ID만 처리 (None이면 모든 책 처리)
    """
    db: Session = SessionLocal()
    
    try:
        # 처리할 책 목록 조회
        if book_id:
            books = db.query(Book).filter(Book.id == book_id).all()
            if not books:
                logger.error(f"[ERROR] Book {book_id} not found")
                return
        else:
            # page_summarized 이상 상태인 책만 처리
            books = db.query(Book).filter(
                Book.status.in_(["page_summarized", "summarized"])
            ).all()
        
        logger.info(f"[INFO] Found {len(books)} books to process")
        
        cache_dir = settings.cache_dir / "summaries"
        total_deleted = 0
        
        for book in books:
            book_title = book.title or f"book_{book.id}"
            # 파일명으로 사용 불가능한 문자 제거
            safe_title = "".join(
                c for c in book_title if c.isalnum() or c in (' ', '-', '_')
            ).strip()
            safe_title = safe_title.replace(' ', '_')[:100]
            
            book_cache_dir = cache_dir / safe_title
            
            if not book_cache_dir.exists():
                logger.warning(
                    f"[WARNING] Cache directory not found for book {book.id}: {book_cache_dir}"
                )
                continue
            
            # 챕터 서머리 캐시만 삭제 (chapter_*.json)
            chapter_files = list(book_cache_dir.glob("chapter_*.json"))
            deleted_count = 0
            
            for cache_file in chapter_files:
                try:
                    cache_file.unlink()
                    deleted_count += 1
                except Exception as e:
                    logger.warning(
                        f"[WARNING] Failed to delete {cache_file}: {e}"
                    )
            
            total_deleted += deleted_count
            logger.info(
                f"[INFO] Book {book.id} ({book_title}): "
                f"Deleted {deleted_count} chapter cache files"
            )
        
        logger.info(
            f"[INFO] Total deleted: {total_deleted} chapter cache files "
            f"from {len(books)} books"
        )
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to delete chapter caches: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        book_id = int(sys.argv[1])
        logger.info(f"[INFO] Deleting chapter caches for book_id={book_id}")
        delete_chapter_caches(book_id=book_id)
    else:
        logger.info("[INFO] Deleting chapter caches for all books")
        delete_chapter_caches()

