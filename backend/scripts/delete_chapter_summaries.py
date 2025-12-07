"""
특정 책의 ChapterSummary와 북서머리를 삭제하는 스크립트

사용법:
    poetry run python -m backend.scripts.delete_chapter_summaries <book_id>
"""
import sys
import logging
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.api.database import SessionLocal
from backend.api.models.book import ChapterSummary, Book
from backend.config.settings import settings

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """메인 함수"""
    if len(sys.argv) < 2:
        print("Usage: poetry run python -m backend.scripts.delete_chapter_summaries <book_id>")
        sys.exit(1)
    
    try:
        book_id = int(sys.argv[1])
    except ValueError:
        print(f"Error: Invalid book_id: {sys.argv[1]}")
        sys.exit(1)
    
    db = SessionLocal()
    try:
        # 책 조회
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            print(f"Error: Book {book_id} not found")
            sys.exit(1)
        
        # 1. ChapterSummary 삭제
        chapter_summaries = db.query(ChapterSummary).filter(ChapterSummary.book_id == book_id).all()
        
        if chapter_summaries:
            print(f"Found {len(chapter_summaries)} chapter summaries for book_id={book_id}")
            for cs in chapter_summaries:
                db.delete(cs)
                print(f"  - Deleted ChapterSummary id={cs.id}, chapter_id={cs.chapter_id}")
            db.commit()
            print(f"[SUCCESS] Deleted {len(chapter_summaries)} chapter summaries")
        else:
            print(f"No chapter summaries found for book_id={book_id}")
        
        # 2. 북서머리 로컬 파일 삭제
        book_summaries_dir = settings.output_dir / "book_summaries"
        if book.title:
            safe_title = "".join(
                c for c in book.title if c.isalnum() or c in (' ', '-', '_')
            ).strip().replace(' ', '_')[:100]
            report_file = book_summaries_dir / f"{safe_title}_report.json"
            if report_file.exists():
                report_file.unlink()
                print(f"[SUCCESS] Deleted book report file: {report_file}")
            else:
                print(f"[INFO] Book report file not found: {report_file}")
        
        # 3. 북서머리 및 챕터 캐시 삭제
        cache_dir = settings.cache_dir / "summaries"
        if book.title:
            safe_title = "".join(
                c for c in book.title if c.isalnum() or c in (' ', '-', '_')
            ).strip().replace(' ', '_')[:100]
            book_cache_dir = cache_dir / safe_title
            if book_cache_dir.exists():
                # book_*.json 파일 삭제
                book_cache_files = list(book_cache_dir.glob("book_*.json"))
                for cache_file in book_cache_files:
                    cache_file.unlink()
                    print(f"  - Deleted book cache: {cache_file.name}")
                if book_cache_files:
                    print(f"[SUCCESS] Deleted {len(book_cache_files)} book cache files")
                else:
                    print(f"[INFO] No book cache files found in {book_cache_dir}")
                
                # chapter_*.json 파일 삭제
                chapter_cache_files = list(book_cache_dir.glob("chapter_*.json"))
                for cache_file in chapter_cache_files:
                    cache_file.unlink()
                    print(f"  - Deleted chapter cache: {cache_file.name}")
                if chapter_cache_files:
                    print(f"[SUCCESS] Deleted {len(chapter_cache_files)} chapter cache files")
                else:
                    print(f"[INFO] No chapter cache files found in {book_cache_dir}")
        
        print(f"\n[COMPLETE] Cleanup completed for book_id={book_id}")
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to delete: {e}", exc_info=True)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()

