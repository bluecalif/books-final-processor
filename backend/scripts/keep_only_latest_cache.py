"""
최신 캐시만 남기고 나머지 백업으로 이동

각 챕터별로 (chapter_number + chapter_title 기준) 가장 최신 캐시 파일만 유지하고 나머지는 backup/으로 이동합니다.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def keep_only_latest_cache(cache_base_dir: Path) -> Dict[str, Any]:
    """최신 캐시만 남기고 나머지 백업으로 이동"""
    stats = {
        "total_books": 0,
        "books_processed": 0,
        "total_chapter_groups": 0,
        "files_kept": 0,
        "files_moved_to_backup": 0,
        "errors": 0,
    }
    
    # 각 책별 디렉토리 찾기
    book_dirs = [d for d in cache_base_dir.iterdir() if d.is_dir() and d.name != "backup"]
    stats["total_books"] = len(book_dirs)
    
    for book_dir in book_dirs:
        logger.info(f"[INFO] Processing: {book_dir.name}")
        
        # 챕터 캐시 파일 찾기
        chapter_files = list(book_dir.glob("chapter_*.json"))
        
        if not chapter_files:
            continue
        
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
                    # 파일 정보 저장 (파일 경로, cached_at, mtime)
                    cached_at = data.get("cached_at", 0)
                    mtime = chapter_file.stat().st_mtime
                    chapter_groups[key].append({
                        "file": chapter_file,
                        "cached_at": cached_at,
                        "mtime": mtime,
                        "data": data,
                    })
                else:
                    # 메타 정보가 없는 파일은 별도 처리 (나중에)
                    logger.warning(
                        f"[WARNING] Cache file {chapter_file.name} has no chapter_number or chapter_title"
                    )
            except Exception as e:
                logger.error(f"[ERROR] Failed to read {chapter_file.name}: {e}")
                stats["errors"] += 1
        
        stats["total_chapter_groups"] += len(chapter_groups)
        
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
        
        stats["books_processed"] += 1
    
    return stats


def main():
    """메인 함수"""
    from backend.config.settings import settings
    
    cache_base_dir = settings.cache_dir / "summaries"
    
    if not cache_base_dir.exists():
        logger.warning(f"[WARNING] Cache base directory not found: {cache_base_dir}")
        return
    
    logger.info(f"[INFO] Starting cache cleanup (keep only latest)...")
    logger.info(f"[INFO] Cache directory: {cache_base_dir}")
    
    stats = keep_only_latest_cache(cache_base_dir)
    
    logger.info(f"\n{'='*80}")
    logger.info("최신 캐시만 유지 완료")
    logger.info(f"{'='*80}")
    logger.info(f"처리된 도서: {stats['books_processed']}/{stats['total_books']}")
    logger.info(f"챕터 그룹: {stats['total_chapter_groups']}")
    logger.info(f"유지된 파일: {stats['files_kept']}")
    logger.info(f"백업으로 이동: {stats['files_moved_to_backup']}")
    logger.info(f"오류: {stats['errors']}")
    logger.info(f"{'='*80}\n")


if __name__ == "__main__":
    main()

