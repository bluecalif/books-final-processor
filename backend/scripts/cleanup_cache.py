"""
캐시 파일 정리 스크립트 (표준)

1. .backup 파일들을 backup/ 폴더로 이동
2. .tmp 파일 삭제
3. 각 챕터별로 최신 캐시만 유지하고 나머지는 backup/으로 이동
4. 정리 결과 리포트 출력

사용법:
    poetry run python -m backend.scripts.cleanup_cache [book_id1] [book_id2] ...
    (book_id 없으면 모든 도서 처리)
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
logger = logging.getLogger(__name__)


def cleanup_backup_files(book_dir: Path) -> Dict[str, int]:
    """백업 파일들을 backup/ 폴더로 이동"""
    stats = {
        "backup_files_found": 0,
        "backup_files_moved": 0,
        "errors": 0,
    }
    
    backup_files = list(book_dir.glob("*.backup"))
    stats["backup_files_found"] = len(backup_files)
    
    if backup_files:
        backup_dir = book_dir / "backup"
        backup_dir.mkdir(exist_ok=True)
        
        for backup_file in backup_files:
            try:
                target_path = backup_dir / backup_file.name
                if target_path.exists():
                    # 이미 있으면 삭제
                    backup_file.unlink()
                    stats["backup_files_moved"] += 1
                    logger.debug(f"[DEBUG] Deleted duplicate backup: {backup_file.name}")
                else:
                    # backup 폴더로 이동
                    backup_file.rename(target_path)
                    stats["backup_files_moved"] += 1
                    logger.debug(f"[DEBUG] Moved backup file: {backup_file.name}")
            except Exception as e:
                logger.error(f"[ERROR] Failed to move {backup_file.name}: {e}")
                stats["errors"] += 1
    
    return stats


def cleanup_temp_files(book_dir: Path) -> Dict[str, int]:
    """임시 파일(.tmp) 삭제"""
    stats = {
        "tmp_files_found": 0,
        "tmp_files_deleted": 0,
        "errors": 0,
    }
    
    tmp_files = list(book_dir.glob("*.tmp"))
    stats["tmp_files_found"] = len(tmp_files)
    
    for tmp_file in tmp_files:
        try:
            tmp_file.unlink()
            stats["tmp_files_deleted"] += 1
            logger.debug(f"[DEBUG] Deleted temp file: {tmp_file.name}")
        except Exception as e:
            logger.error(f"[ERROR] Failed to delete {tmp_file.name}: {e}")
            stats["errors"] += 1
    
    return stats


def keep_only_latest_chapter_cache(book_dir: Path) -> Dict[str, int]:
    """각 챕터별로 최신 캐시만 유지하고 나머지는 backup으로 이동"""
    stats = {
        "chapter_files_found": 0,
        "chapter_groups": 0,
        "files_kept": 0,
        "files_moved_to_backup": 0,
        "errors": 0,
    }
    
    chapter_files = list(book_dir.glob("chapter_*.json"))
    stats["chapter_files_found"] = len(chapter_files)
    
    if not chapter_files:
        return stats
    
    # chapter_number와 chapter_title로 그룹화
    chapter_groups = defaultdict(list)
    
    for chapter_file in chapter_files:
        try:
            with open(chapter_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            chapter_number = data.get("chapter_number")
            chapter_title = data.get("chapter_title")
            
            if chapter_number and chapter_title:
                key = f"{chapter_number}_{chapter_title}"
                cached_at = data.get("cached_at", 0)
                mtime = chapter_file.stat().st_mtime
                chapter_groups[key].append({
                    "file": chapter_file,
                    "cached_at": cached_at,
                    "mtime": mtime,
                    "data": data,
                })
            else:
                # 메타 정보가 없는 파일은 별도 처리
                logger.warning(
                    f"[WARNING] Cache file {chapter_file.name} has no chapter_number or chapter_title"
                )
        except Exception as e:
            logger.error(f"[ERROR] Failed to read {chapter_file.name}: {e}")
            stats["errors"] += 1
    
    stats["chapter_groups"] = len(chapter_groups)
    
    # backup 폴더 생성
    backup_dir = book_dir / "backup"
    backup_dir.mkdir(exist_ok=True)
    
    # 각 챕터 그룹에서 최신 파일만 유지
    for key, files in chapter_groups.items():
        if len(files) == 1:
            # 파일이 1개면 그대로 유지
            stats["files_kept"] += 1
            continue
        
        # 가장 최신 파일 찾기 (cached_at 우선, 없으면 mtime)
        files.sort(key=lambda x: (x["cached_at"] or 0, x["mtime"]), reverse=True)
        keep_file = files[0]["file"]
        duplicate_files = files[1:]
        
        logger.info(
            f"[INFO] {book_dir.name}: chapter={key}, "
            f"keeping={keep_file.name}, duplicates={len(duplicate_files)}"
        )
        
        stats["files_kept"] += 1
        
        # 중복 파일들을 backup으로 이동
        for dup_info in duplicate_files:
            dup_file = dup_info["file"]
            try:
                backup_path = backup_dir / f"{dup_file.stem}_old{dup_file.suffix}"
                dup_file.rename(backup_path)
                stats["files_moved_to_backup"] += 1
                logger.debug(f"[DEBUG] Moved to backup: {dup_file.name}")
            except Exception as e:
                logger.error(f"[ERROR] Failed to move {dup_file.name}: {e}")
                stats["errors"] += 1
    
    return stats


def cleanup_book_cache(book_dir: Path) -> Dict[str, Any]:
    """특정 도서의 캐시 정리"""
    logger.info(f"[INFO] Processing: {book_dir.name}")
    
    # 1. 백업 파일 정리
    backup_stats = cleanup_backup_files(book_dir)
    
    # 2. 임시 파일 삭제
    tmp_stats = cleanup_temp_files(book_dir)
    
    # 3. 최신 캐시만 유지
    chapter_stats = keep_only_latest_chapter_cache(book_dir)
    
    return {
        "book_name": book_dir.name,
        "backup": backup_stats,
        "temp": tmp_stats,
        "chapters": chapter_stats,
    }


def main():
    """메인 함수"""
    import sys
    from backend.config.settings import settings
    
    cache_base_dir = settings.cache_dir / "summaries"
    
    if not cache_base_dir.exists():
        logger.warning(f"[WARNING] Cache base directory not found: {cache_base_dir}")
        return
    
    # Book ID 지정 여부 확인
    if len(sys.argv) > 1:
        # 특정 도서만 처리
        book_ids = [int(bid) for bid in sys.argv[1:]]
        from backend.api.database import SessionLocal
        from backend.api.models.book import Book
        
        db = SessionLocal()
        try:
            book_titles = []
            for book_id in book_ids:
                book = db.query(Book).filter(Book.id == book_id).first()
                if book:
                    book_titles.append(book.title or f"book_{book_id}")
                else:
                    logger.warning(f"[WARNING] Book {book_id} not found")
            db.close()
        except Exception as e:
            logger.error(f"[ERROR] Failed to query books: {e}")
            db.close()
            return
        
        book_dirs = [cache_base_dir / title for title in book_titles if (cache_base_dir / title).exists()]
    else:
        # 모든 도서 처리
        book_dirs = [d for d in cache_base_dir.iterdir() if d.is_dir() and d.name != "backup"]
    
    if not book_dirs:
        logger.warning("[WARNING] No book cache directories found")
        return
    
    logger.info(f"[INFO] Starting cache cleanup...")
    logger.info(f"[INFO] Cache directory: {cache_base_dir}")
    logger.info(f"[INFO] Processing {len(book_dirs)} book(s)")
    
    total_stats = {
        "total_books": len(book_dirs),
        "books_processed": 0,
        "total_backup_files_moved": 0,
        "total_tmp_files_deleted": 0,
        "total_chapter_files_kept": 0,
        "total_chapter_files_moved": 0,
        "total_errors": 0,
    }
    
    for book_dir in book_dirs:
        try:
            stats = cleanup_book_cache(book_dir)
            total_stats["books_processed"] += 1
            total_stats["total_backup_files_moved"] += stats["backup"]["backup_files_moved"]
            total_stats["total_tmp_files_deleted"] += stats["temp"]["tmp_files_deleted"]
            total_stats["total_chapter_files_kept"] += stats["chapters"]["files_kept"]
            total_stats["total_chapter_files_moved"] += stats["chapters"]["files_moved_to_backup"]
            total_stats["total_errors"] += (
                stats["backup"]["errors"] +
                stats["temp"]["errors"] +
                stats["chapters"]["errors"]
            )
        except Exception as e:
            logger.error(f"[ERROR] Failed to process {book_dir.name}: {e}")
            total_stats["total_errors"] += 1
    
    # 최종 리포트
    logger.info(f"\n{'='*80}")
    logger.info("캐시 정리 완료")
    logger.info(f"{'='*80}")
    logger.info(f"처리된 도서: {total_stats['books_processed']}/{total_stats['total_books']}")
    logger.info(f"백업 파일 이동: {total_stats['total_backup_files_moved']}")
    logger.info(f"임시 파일 삭제: {total_stats['total_tmp_files_deleted']}")
    logger.info(f"챕터 캐시 유지: {total_stats['total_chapter_files_kept']}")
    logger.info(f"챕터 캐시 백업 이동: {total_stats['total_chapter_files_moved']}")
    logger.info(f"오류: {total_stats['total_errors']}")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    main()

