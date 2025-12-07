"""
기존 챕터 서머리 캐시에 page_count 메타 정보 추가

DB에서 Chapter 정보를 조회하여 각 챕터 서머리 캐시 파일에 page_count를 추가합니다.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.api.database import SessionLocal
from backend.api.models.book import Book, Chapter, ChapterSummary
from backend.summarizers.summary_cache_manager import SummaryCacheManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_chapter_page_count(book_id: int, db: Session) -> Dict[int, int]:
    """
    DB에서 챕터별 페이지 수 조회
    
    Returns:
        {chapter_id: page_count}
    """
    chapters = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id)
        .all()
    )
    
    chapter_page_count = {}
    for chapter in chapters:
        page_count = chapter.end_page - chapter.start_page + 1
        chapter_page_count[chapter.id] = page_count
    
    return chapter_page_count


def match_cache_file_to_chapter(
    cache_file: Path, book_id: int, db: Session, chapter_summaries: list
) -> Optional[ChapterSummary]:
    """
    캐시 파일을 ChapterSummary와 매칭 (core_message 비교)
    """
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        cache_core_message = cache_data.get("core_message", "")
        cache_content_hash = cache_data.get("content_hash", "")
        
        if not cache_core_message:
            return None
        
        # 방법 1: content_hash로 매칭
        if cache_content_hash:
            for cs in chapter_summaries:
                if cs.structured_data:
                    cs_hash = cs.structured_data.get("content_hash", "")
                    if cs_hash == cache_content_hash:
                        return cs
        
        # 방법 2: core_message 비교
        for cs in chapter_summaries:
            if cs.structured_data:
                cs_core_message = cs.structured_data.get("core_message", "")
                if cs_core_message and len(cs_core_message) > 50:
                    if cs_core_message[:100] == cache_core_message[:100]:
                        return cs
        
        return None
        
    except Exception as e:
        logger.warning(f"[WARNING] Failed to match cache file {cache_file.name}: {e}")
        return None


def add_page_count_to_cache_file(
    cache_file: Path, page_count: int
) -> bool:
    """
    캐시 파일에 page_count 추가
    
    Returns:
        성공 여부
    """
    try:
        # 기존 파일 읽기
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # 이미 page_count가 있으면 스킵
        if "page_count" in cache_data:
            logger.debug(f"[SKIP] Cache file {cache_file.name} already has page_count")
            return True
        
        # 백업 파일 생성
        backup_file = cache_file.with_suffix('.backup')
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        # page_count 추가
        cache_data["page_count"] = page_count
        
        # 임시 파일로 저장
        temp_file = cache_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        # 원자적 이동
        temp_file.replace(cache_file)
        
        logger.info(
            f"[INFO] Added page_count to {cache_file.name}: page_count={page_count}"
        )
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to add page_count to {cache_file.name}: {e}")
        return False


def process_book_cache(book_id: int, db: Session) -> Dict[str, Any]:
    """
    특정 도서의 캐시 파일 처리
    
    Returns:
        처리 통계
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        logger.error(f"[ERROR] Book {book_id} not found")
        return {"success": False, "error": "Book not found"}
    
    book_title = book.title or f"book_{book_id}"
    logger.info(f"[INFO] Processing cache for book {book_id}: {book_title}")
    
    # 챕터별 페이지 수 조회
    chapter_page_count = get_chapter_page_count(book_id, db)
    logger.info(f"[INFO] Found {len(chapter_page_count)} chapters in DB")
    
    # 캐시 디렉토리 확인
    cache_manager = SummaryCacheManager(book_title=book_title)
    cache_dir = cache_manager.cache_dir
    
    if not cache_dir.exists():
        logger.warning(f"[WARNING] Cache directory not found: {cache_dir}")
        return {"success": False, "error": "Cache directory not found"}
    
    # 챕터 서머리 캐시 파일 찾기
    chapter_cache_files = list(cache_dir.glob("chapter_*.json"))
    logger.info(f"[INFO] Found {len(chapter_cache_files)} chapter cache files")
    
    # ChapterSummary와 매칭하여 처리
    chapter_summaries = (
        db.query(ChapterSummary)
        .filter(ChapterSummary.book_id == book_id)
        .all()
    )
    
    stats = {
        "total_files": len(chapter_cache_files),
        "processed": 0,
        "skipped": 0,
        "failed": 0,
        "added_page_count": 0,
    }
    
    for cache_file in chapter_cache_files:
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 이미 page_count가 있으면 스킵
            if "page_count" in cache_data:
                stats["skipped"] += 1
                continue
            
            # ChapterSummary와 매칭
            matched_cs = match_cache_file_to_chapter(cache_file, book_id, db, chapter_summaries)
            
            if matched_cs:
                chapter_id = matched_cs.chapter_id
                if chapter_id in chapter_page_count:
                    page_count = chapter_page_count[chapter_id]
                    
                    if add_page_count_to_cache_file(cache_file, page_count):
                        stats["processed"] += 1
                        stats["added_page_count"] += 1
                    else:
                        stats["failed"] += 1
                else:
                    logger.warning(
                        f"[WARNING] Chapter {chapter_id} not found in chapter_page_count "
                        f"for cache file {cache_file.name}"
                    )
                    stats["skipped"] += 1
            else:
                # 매칭 실패 시, 캐시 파일의 chapter_number와 chapter_title로 직접 찾기
                chapter_number = cache_data.get("chapter_number")
                chapter_title = cache_data.get("chapter_title")
                
                if chapter_number and chapter_title:
                    # DB에서 직접 찾기
                    chapter = (
                        db.query(Chapter)
                        .filter(
                            Chapter.book_id == book_id,
                            Chapter.order_index == chapter_number - 1,  # 0-based
                            Chapter.title == chapter_title
                        )
                        .first()
                    )
                    
                    if chapter:
                        page_count = chapter.end_page - chapter.start_page + 1
                        if add_page_count_to_cache_file(cache_file, page_count):
                            stats["processed"] += 1
                            stats["added_page_count"] += 1
                        else:
                            stats["failed"] += 1
                    else:
                        logger.warning(
                            f"[WARNING] Could not find chapter: number={chapter_number}, "
                            f"title={chapter_title} for cache file {cache_file.name}"
                        )
                        stats["skipped"] += 1
                else:
                    logger.warning(
                        f"[WARNING] Could not match cache file {cache_file.name} "
                        f"and no chapter metadata found"
                    )
                    stats["skipped"] += 1
                
        except Exception as e:
            logger.error(f"[ERROR] Failed to process {cache_file.name}: {e}")
            stats["failed"] += 1
    
    stats["success"] = True
    return stats


def main():
    """메인 함수"""
    import sys
    
    # Book ID (기본값: 모든 summary가 생성된 도서)
    if len(sys.argv) > 1:
        book_ids = [int(bid) for bid in sys.argv[1:]]
    else:
        # 모든 summary가 생성된 도서 조회
        db = SessionLocal()
        try:
            from backend.api.models.book import BookStatus
            books = (
                db.query(Book)
                .filter(Book.status >= BookStatus.PAGE_SUMMARIZED)
                .all()
            )
            book_ids = [book.id for book in books]
            logger.info(f"[INFO] Found {len(book_ids)} books with summaries")
        finally:
            db.close()
    
    if not book_ids:
        logger.warning("[WARNING] No books to process")
        return
    
    total_stats = {
        "total_books": len(book_ids),
        "books_processed": 0,
        "books_failed": 0,
        "total_files_processed": 0,
        "total_page_count_added": 0,
    }
    
    for book_id in book_ids:
        db = SessionLocal()
        try:
            stats = process_book_cache(book_id, db)
            if stats.get("success"):
                total_stats["books_processed"] += 1
                total_stats["total_files_processed"] += stats.get("processed", 0)
                total_stats["total_page_count_added"] += stats.get("added_page_count", 0)
            else:
                total_stats["books_failed"] += 1
        finally:
            db.close()
    
    logger.info(f"\n{'='*80}")
    logger.info("캐시 page_count 추가 완료")
    logger.info(f"{'='*80}")
    logger.info(f"처리된 도서: {total_stats['books_processed']}/{total_stats['total_books']}")
    logger.info(f"실패한 도서: {total_stats['books_failed']}")
    logger.info(f"처리된 파일: {total_stats['total_files_processed']}")
    logger.info(f"page_count 추가: {total_stats['total_page_count_added']}")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    main()

