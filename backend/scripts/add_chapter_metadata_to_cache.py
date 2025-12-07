"""
기존 챕터 서머리 캐시에 chapter_number, chapter_title 메타 정보 추가

DB에서 Chapter 정보를 조회하여 각 챕터 서머리 캐시 파일에 메타 정보를 추가합니다.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.api.database import SessionLocal
from backend.api.models.book import Book, Chapter, ChapterSummary
from backend.summarizers.summary_cache_manager import SummaryCacheManager
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_chapter_info_from_db(book_id: int, db: Session) -> Dict[int, Dict[str, Any]]:
    """
    DB에서 챕터 정보 조회
    
    Returns:
        {chapter_id: {"chapter_number": int, "chapter_title": str}}
    """
    chapters = (
        db.query(Chapter)
        .filter(Chapter.book_id == book_id)
        .all()
    )
    
    chapter_info = {}
    for chapter in chapters:
        chapter_info[chapter.id] = {
            "chapter_number": chapter.order_index + 1,  # 1-based
            "chapter_title": chapter.title,
        }
    
    return chapter_info


def match_cache_file_to_chapter(
    cache_file: Path, book_id: int, db: Session, chapter_summaries: List[ChapterSummary]
) -> Optional[ChapterSummary]:
    """
    캐시 파일을 ChapterSummary와 매칭 (core_message 비교)
    
    Returns:
        매칭된 ChapterSummary 또는 None
    """
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        cache_core_message = cache_data.get("core_message", "")
        if not cache_core_message:
            return None
        
        # ChapterSummary의 structured_data와 core_message 비교
        for cs in chapter_summaries:
            if cs.structured_data:
                cs_core_message = cs.structured_data.get("core_message", "")
                # 처음 100자 비교 (더 정확한 매칭)
                if cs_core_message and len(cs_core_message) > 50:
                    if cs_core_message[:100] == cache_core_message[:100]:
                        return cs
                elif cs_core_message and len(cs_core_message) > 20:
                    # 짧은 경우 50자 비교
                    if cs_core_message[:50] == cache_core_message[:50]:
                        return cs
        
        return None
        
    except Exception as e:
        logger.warning(f"[WARNING] Failed to match cache file {cache_file.name}: {e}")
        return None


def add_metadata_to_cache_file(
    cache_file: Path, chapter_number: int, chapter_title: str
) -> bool:
    """
    캐시 파일에 chapter_number, chapter_title 추가
    
    Returns:
        성공 여부
    """
    try:
        # 기존 파일 읽기
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # 이미 메타 정보가 있으면 스킵
        if "chapter_number" in cache_data and "chapter_title" in cache_data:
            logger.debug(f"[SKIP] Cache file {cache_file.name} already has metadata")
            return True
        
        # 백업 파일 생성
        backup_file = cache_file.with_suffix('.backup')
        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        # 메타 정보 추가
        cache_data["chapter_number"] = chapter_number
        cache_data["chapter_title"] = chapter_title
        
        # 임시 파일로 저장
        temp_file = cache_file.with_suffix('.tmp')
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=2)
        
        # 원자적 이동
        temp_file.replace(cache_file)
        
        logger.info(
            f"[INFO] Added metadata to {cache_file.name}: "
            f"chapter_number={chapter_number}, chapter_title={chapter_title}"
        )
        return True
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to add metadata to {cache_file.name}: {e}")
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
    
    # 챕터 정보 조회
    chapter_info = get_chapter_info_from_db(book_id, db)
    logger.info(f"[INFO] Found {len(chapter_info)} chapters in DB")
    
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
        "added_metadata": 0,
    }
    
    # 각 캐시 파일을 ChapterSummary와 매칭
    processed_files = set()
    
    for cache_file in chapter_cache_files:
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 이미 메타 정보가 있으면 스킵
            if "chapter_number" in cache_data and "chapter_title" in cache_data:
                stats["skipped"] += 1
                processed_files.add(cache_file)
                continue
            
            # ChapterSummary와 매칭
            matched_cs = match_cache_file_to_chapter(cache_file, book_id, db, chapter_summaries)
            
            if matched_cs:
                chapter_id = matched_cs.chapter_id
                if chapter_id in chapter_info:
                    chapter_num = chapter_info[chapter_id]["chapter_number"]
                    chapter_title = chapter_info[chapter_id]["chapter_title"]
                    
                    if add_metadata_to_cache_file(cache_file, chapter_num, chapter_title):
                        stats["processed"] += 1
                        stats["added_metadata"] += 1
                        processed_files.add(cache_file)
                    else:
                        stats["failed"] += 1
                else:
                    logger.warning(
                        f"[WARNING] Chapter {chapter_id} not found in chapter_info "
                        f"for cache file {cache_file.name}"
                    )
                    stats["skipped"] += 1
            else:
                logger.warning(
                    f"[WARNING] Could not match cache file {cache_file.name} to any ChapterSummary"
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
        "total_metadata_added": 0,
    }
    
    for book_id in book_ids:
        db = SessionLocal()
        try:
            stats = process_book_cache(book_id, db)
            if stats.get("success"):
                total_stats["books_processed"] += 1
                total_stats["total_files_processed"] += stats.get("processed", 0)
                total_stats["total_metadata_added"] += stats.get("added_metadata", 0)
            else:
                total_stats["books_failed"] += 1
        finally:
            db.close()
    
    logger.info(f"\n{'='*80}")
    logger.info("캐시 메타 정보 추가 완료")
    logger.info(f"{'='*80}")
    logger.info(f"처리된 도서: {total_stats['books_processed']}/{total_stats['total_books']}")
    logger.info(f"실패한 도서: {total_stats['books_failed']}")
    logger.info(f"처리된 파일: {total_stats['total_files_processed']}")
    logger.info(f"메타 정보 추가: {total_stats['total_metadata_added']}")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    main()

