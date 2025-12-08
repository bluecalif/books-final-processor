"""
특정 책의 ChapterSummary와 북서머리 삭제 상태 확인 스크립트

사용법:
    poetry run python -m backend.scripts.verify_cleanup <book_id>
"""
import sys
import logging
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.api.database import SessionLocal
from backend.api.models.book import ChapterSummary, Book, Chapter
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
        print("Usage: poetry run python -m backend.scripts.verify_cleanup <book_id>")
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
        
        print(f"\n{'='*60}")
        print(f"Cleanup Verification for Book {book_id}: {book.title}")
        print(f"{'='*60}\n")
        
        # 1. DB ChapterSummary 확인
        chapter_summaries = db.query(ChapterSummary).filter(ChapterSummary.book_id == book_id).all()
        print(f"[DB] ChapterSummary count: {len(chapter_summaries)}")
        if chapter_summaries:
            print("  - WARNING: ChapterSummary still exists in DB:")
            for cs in chapter_summaries:
                chapter = db.query(Chapter).filter(Chapter.id == cs.chapter_id).first()
                chapter_title = chapter.title if chapter else "Unknown"
                print(f"    * id={cs.id}, chapter_id={cs.chapter_id}, title={chapter_title}")
        else:
            print("  - OK: No ChapterSummary in DB")
        
        # 2. Chapter 테이블 확인 (참고용)
        chapters = db.query(Chapter).filter(Chapter.book_id == book_id).order_by(Chapter.order_index).all()
        print(f"\n[DB] Chapter count: {len(chapters)}")
        print("  - Chapter list:")
        for ch in chapters:
            print(f"    * order_index={ch.order_index}, id={ch.id}, title={ch.title}, "
                  f"pages={ch.start_page}-{ch.end_page} (count={ch.end_page - ch.start_page + 1})")
        
        # 3. 북서머리 로컬 파일 확인
        book_summaries_dir = settings.output_dir / "book_summaries"
        if book.title:
            safe_title = "".join(
                c for c in book.title if c.isalnum() or c in (' ', '-', '_')
            ).strip().replace(' ', '_')[:100]
            report_file = book_summaries_dir / f"{safe_title}_report.json"
            print(f"\n[FILE] Book report file: {report_file}")
            if report_file.exists():
                print(f"  - WARNING: File still exists: {report_file}")
            else:
                print("  - OK: File deleted")
        
        # 4. 북서머리 캐시 확인
        cache_dir = settings.cache_dir / "summaries"
        if book.title:
            safe_title = "".join(
                c for c in book.title if c.isalnum() or c in (' ', '-', '_')
            ).strip().replace(' ', '_')[:100]
            book_cache_dir = cache_dir / safe_title
            print(f"\n[CACHE] Book cache directory: {book_cache_dir}")
            if book_cache_dir.exists():
                book_cache_files = list(book_cache_dir.glob("book_*.json"))
                print(f"  - Book cache files count: {len(book_cache_files)}")
                if book_cache_files:
                    print("  - WARNING: Book cache files still exist:")
                    for cache_file in book_cache_files:
                        print(f"    * {cache_file.name}")
                else:
                    print("  - OK: No book cache files")
            else:
                print("  - OK: Cache directory does not exist")
        
        # 5. 챕터 캐시 확인 (2페이지 이하 챕터는 스킵되어 있어야 함)
        if book_cache_dir.exists():
            chapter_cache_files = list(book_cache_dir.glob("chapter_*.json"))
            print(f"\n[CACHE] Chapter cache files count: {len(chapter_cache_files)}")
            print("  - Chapter cache files (should match processed chapters):")
            for cache_file in sorted(chapter_cache_files):
                # 캐시 파일에서 페이지 수 확인
                try:
                    import json
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    page_count = cache_data.get('page_count', 'N/A')
                    chapter_title = cache_data.get('chapter_title', 'N/A')
                    chapter_number = cache_data.get('chapter_number', 'N/A')
                    print(f"    * {cache_file.name}")
                    print(f"      - chapter_number={chapter_number}, title={chapter_title}, page_count={page_count}")
                except Exception as e:
                    print(f"    * {cache_file.name} (error reading: {e})")
        
        print(f"\n{'='*60}")
        print("Verification Summary:")
        print(f"  - ChapterSummary in DB: {len(chapter_summaries)} (should be 0)")
        print(f"  - Book report file: {'EXISTS' if report_file.exists() else 'DELETED'}")
        print(f"  - Book cache files: {len(book_cache_files) if book_cache_dir.exists() else 0} (should be 0)")
        print(f"  - Chapter cache files: {len(chapter_cache_files) if book_cache_dir.exists() else 0} (should match processed chapters)")
        print(f"{'='*60}\n")
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to verify: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()



